"""Send my own posts to my TikTok inbox as drafts (Content Posting API, upload mode).

Runs inside GitHub Actions. Secrets come from environment variables:
  TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TOKEN_PASSPHRASE
The refresh token is kept encrypted in state/tiktok_token.enc (AES-256, key = TOKEN_PASSPHRASE).

Commands:
  python tools/tiktok.py exchange CODE   # one-time: turn the sign-in code into a stored token
  python tools/tiktok.py whoami          # check the stored token works
  python tools/tiktok.py send [N]        # send the N oldest folders in outbox/ (default 1) to the TikTok inbox
"""
import json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://open.tiktokapis.com/v2"
REDIRECT_URI = "https://ldumont1007.github.io/callback/"
SITE = "https://ldumont1007.github.io"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state" / "tiktok_token.enc"
OUTBOX = ROOT / "outbox"
SENT_LOG = ROOT / "state" / "sent.log"


def env(name):
    v = os.environ.get(name, "").strip()
    if not v: sys.exit(f"Missing secret {name}. Add it in GitHub: Settings > Secrets and variables > Actions.")
    return v


def mask(value):  # hide a value from GitHub Actions logs
    if value and os.environ.get("GITHUB_ACTIONS"): print(f"::add-mask::{value}", flush=True)


def http(method, url, data=None, headers=None, form=False, raw=None):
    headers = dict(headers or {})
    body = None
    if raw is not None: body = raw
    elif form: body = urllib.parse.urlencode(data).encode(); headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None: body = json.dumps(data).encode(); headers["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            txt = r.read().decode() or "{}"
            return r.status, (json.loads(txt) if txt.strip().startswith(("{", "[")) else {"raw": txt})
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try: return e.code, json.loads(txt)
        except ValueError: return e.code, {"raw": txt}


# ---------- encrypted token storage ----------
def save_state(obj):
    STATE.parent.mkdir(exist_ok=True)
    p = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt", "-a", "-A",
                        "-pass", "env:TOKEN_PASSPHRASE"], input=json.dumps(obj).encode(), capture_output=True, check=True)
    STATE.write_bytes(p.stdout + b"\n")


def load_state():
    if not STATE.exists(): sys.exit("No stored TikTok token yet. Run the 'TikTok sign-in' workflow first.")
    p = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-a", "-A",
                        "-pass", "env:TOKEN_PASSPHRASE"], input=STATE.read_bytes().strip(), capture_output=True)
    if p.returncode: sys.exit("Could not decrypt the stored token: TOKEN_PASSPHRASE changed? Sign in again.")
    return json.loads(p.stdout)


def token_request(fields):
    fields = {"client_key": env("TIKTOK_CLIENT_KEY"), "client_secret": env("TIKTOK_CLIENT_SECRET"), **fields}
    status, d = http("POST", f"{API}/oauth/token/", fields, {"Cache-Control": "no-cache"}, form=True)
    if status != 200 or "access_token" not in d:
        sys.exit(f"TikTok token request failed ({status}): {d.get('error')} {d.get('error_description', d)}")
    mask(d["access_token"]); mask(d.get("refresh_token"))
    return d


def access_token():
    st = load_state()
    d = token_request({"grant_type": "refresh_token", "refresh_token": st["refresh_token"]})
    if d.get("refresh_token") and d["refresh_token"] != st["refresh_token"]:
        st["refresh_token"] = d["refresh_token"]; st["refreshed"] = int(time.time()); save_state(st)
    return d["access_token"]


# ---------- commands ----------
def cmd_exchange(code):
    code = urllib.parse.unquote(code.strip())
    mask(code)
    d = token_request({"code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI})
    save_state({"refresh_token": d["refresh_token"], "open_id": d.get("open_id"), "scope": d.get("scope"),
                "created": int(time.time())})
    print(f"Signed in. Scopes granted: {d.get('scope')}. Refresh token valid ~{int(d.get('refresh_expires_in', 0)) // 86400} days.")
    whoami(d["access_token"])


def whoami(tok=None):
    tok = tok or access_token()
    status, d = http("GET", f"{API}/user/info/?fields=open_id,display_name", headers={"Authorization": f"Bearer {tok}"})
    user = (d.get("data") or {}).get("user") or {}
    if status == 200 and user: print(f"Connected TikTok account: {user.get('display_name')}")
    else: sys.exit(f"User info failed ({status}): {d.get('error')}")


def api_post(tok, path, payload):
    status, d = http("POST", f"{API}{path}", payload, {"Authorization": f"Bearer {tok}"})
    err = d.get("error") or {}
    if status != 200 or err.get("code") not in (None, "ok"):
        raise RuntimeError(f"{path} failed ({status}): {err.get('code')} {err.get('message')}")
    return d.get("data") or {}


def wait_status(tok, publish_id, limit=90):
    t0 = time.time(); last = None
    while time.time() - t0 < limit:
        d = api_post(tok, "/post/publish/status/fetch/", {"publish_id": publish_id})
        s = d.get("status")
        if s != last: print(f"   status: {s}", flush=True); last = s
        if s in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"): return s
        if s == "FAILED": raise RuntimeError(f"TikTok processing failed: {d.get('fail_reason')}")
        time.sleep(5)
    return last or "UNKNOWN"


def send_video(tok, path):
    size = path.stat().st_size
    if size <= 64 * 1024 * 1024: chunk, count = size, 1
    else: chunk = 10 * 1024 * 1024; count = size // chunk
    d = api_post(tok, "/post/publish/inbox/video/init/",
                 {"source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
    pid, url = d["publish_id"], d["upload_url"]
    with path.open("rb") as f:
        for i in range(count):
            start = i * chunk; end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start); blob = f.read(end - start + 1)
            st, r = http("PUT", url, raw=blob, headers={"Content-Type": "video/mp4", "Content-Length": str(len(blob)),
                                                         "Content-Range": f"bytes {start}-{end}/{size}"})
            if st not in (200, 201, 206): raise RuntimeError(f"Video upload chunk {i + 1}/{count} failed ({st}): {r}")
    return pid


def wait_public(urls, limit=600):
    t0 = time.time()
    for u in urls:
        while True:
            try:
                with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=30) as r:
                    if r.status == 200: break
            except urllib.error.URLError: pass
            if time.time() - t0 > limit: raise RuntimeError(f"Photo not online yet: {u}")
            time.sleep(15)


def send_photos(tok, folder, photos, caption):
    urls = [f"{SITE}/outbox/{folder.name}/{p.name}" for p in photos]
    print("   waiting for the photos to be online on the site…", flush=True); wait_public(urls)
    title = caption.splitlines()[0][:90] if caption else folder.name
    d = api_post(tok, "/post/publish/content/init/", {
        "post_info": {"title": title, "description": caption[:4000]},
        "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0, "photo_images": urls},
        "post_mode": "MEDIA_UPLOAD", "media_type": "PHOTO"})
    return d["publish_id"]


def cmd_send(limit):
    items = sorted(p for p in OUTBOX.iterdir() if p.is_dir()) if OUTBOX.exists() else []
    print(f"{len(items)} post(s) waiting in the outbox; sending {min(limit, len(items))}.")
    items = items[:limit]
    if not items: print("Outbox is empty, nothing to send."); return
    tok = access_token(); done, failed = [], []
    for folder in items:
        caption = (folder / "caption.txt").read_text().strip() if (folder / "caption.txt").exists() else ""
        videos = sorted(folder.glob("*.mp4"))
        photos = sorted([*folder.glob("*.jpg"), *folder.glob("*.jpeg"), *folder.glob("*.webp")])
        print(f"→ {folder.name}: {'video' if videos else f'{len(photos)} photos'}", flush=True)
        try:
            if videos: pid = send_video(tok, videos[0])
            elif photos: pid = send_photos(tok, folder, photos[:35], caption)
            else: raise RuntimeError("folder has no .mp4 or .jpg file")
            status = wait_status(tok, pid)
            done.append((folder, pid, status, caption)); print(f"   sent to your TikTok inbox ({status})")
        except RuntimeError as e:
            failed.append(folder.name); print(f"   FAILED: {e}")
    SENT_LOG.parent.mkdir(exist_ok=True)
    with SENT_LOG.open("a") as log:
        for folder, pid, status, _ in done:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{folder.name}\t{status}\t{pid}\n")
            subprocess.run(["git", "rm", "-rq", str(folder)], cwd=ROOT, check=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as s:
            for folder, pid, status, caption in done:
                s.write(f"- **{folder.name}**: in your inbox ({status})\n")
                if caption: s.write(f"  - caption to paste:\n\n```\n{caption}\n```\n")
            for n in failed: s.write(f"- **{n}**: failed, see the log\n")
    if failed: sys.exit(f"{len(failed)} item(s) failed: {', '.join(failed)}")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "exchange": cmd_exchange(sys.argv[2] if len(sys.argv) > 2 else env("TIKTOK_CODE"))
    elif c == "whoami": whoami()
    elif c == "send": cmd_send(int(os.environ.get("SEND_LIMIT") or (sys.argv[2] if len(sys.argv) > 2 else 1)))
    else: sys.exit(__doc__)
