"""Render a TikTok photo carousel (1080x1920 JPGs) from a JSON spec.

  python3 tools/render.py SPEC.json OUT_DIR

Formats (spec["format"]): quiz, vote, story, top, budget. See PLAYBOOK.md for the spec of each.
Every post ends with a follow slide (spec["follow"] = one short line).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
CX = 500  # left of centre: keeps text clear of TikTok's right-side buttons
FONT_DIR = os.environ.get("FONT_DIR", "/usr/share/fonts/opentype/inter/")
_fc = {}
def font(w, s):
    k = (w, int(s))
    if k not in _fc: _fc[k] = ImageFont.truetype(os.path.join(FONT_DIR, f"Inter-{w}.otf"), int(s))
    return _fc[k]

BG1, BG2 = (16, 14, 40), (5, 5, 16)
WHITE, MUTED = (245, 245, 250), (165, 167, 196)
COLORS = {"gold": (255, 196, 40), "violet": (130, 140, 255), "teal": (60, 210, 170), "red": (255, 84, 84),
          "blue": (70, 150, 255), "orange": (255, 140, 60)}
GOLD, RED = COLORS["gold"], COLORS["red"]
def col(name, default="gold"): return COLORS.get(name or default, COLORS[default])

# ---------- primitives ----------
def txt(img, s, x, y, f, color):
    asc, desc = f.getmetrics(); w = int(f.getlength(s)) + 8
    L = Image.new("RGBA", (w, asc + desc + 8), (0, 0, 0, 0))
    ImageDraw.Draw(L).text((4, 4), s, font=f, fill=color + (255,) if len(color) == 3 else color)
    img.alpha_composite(L, (max(0, int(x) - 4), max(0, int(y) - 4)))

def ctr(img, s, cx, cy, f, color):
    asc, desc = f.getmetrics(); txt(img, s, cx - f.getlength(s) / 2, cy - (asc + desc) / 2, f, color)

def rrect(img, box, r, fill, outline=None, width=0):
    x0, y0, x1, y1 = [int(v) for v in box]; m = width + 2
    L = Image.new("RGBA", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(L).rounded_rectangle([m, m, m + x1 - x0, m + y1 - y0], r, fill=fill, outline=outline, width=width)
    img.alpha_composite(L, (max(0, x0 - m), max(0, y0 - m)))

def circ(img, cx, cy, r, fill=None, outline=None, width=0):
    r = int(r); m = width + 2
    L = Image.new("RGBA", (2 * r + 2 * m, 2 * r + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(L).ellipse([m, m, m + 2 * r, m + 2 * r], fill=fill, outline=outline, width=width)
    img.alpha_composite(L, (int(cx - r - m), int(cy - r - m)))

def wrap(s, f, maxw):
    s = s.replace(" ?", " ?").replace(" :", " :").replace(" !", " !").replace(" %", " %")
    lines, cur = [], ""
    for w in s.split(" "):
        t = (cur + " " + w).strip()
        if f.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def ctext(img, s, y, f, color, maxw=830, spacing=1.16):
    lh = int(f.size * spacing); lines = wrap(s, f, maxw)
    for i, ln in enumerate(lines): txt(img, ln, CX - f.getlength(ln) / 2, y + i * lh, f, color)
    return y + lh * len(lines)

def ltext(img, s, x, y, f, color, maxw=760, spacing=1.22):
    lh = int(f.size * spacing); lines = wrap(s, f, maxw)
    for i, ln in enumerate(lines): txt(img, ln, x, y + i * lh, f, color)
    return y + lh * len(lines)

def fitsize(s, w, start, maxw, minsize=40):
    z = start
    while z > minsize and max(font(w, z).getlength(x) for x in wrap(s, font(w, z), maxw)) > maxw: z -= 4
    return font(w, z)

def fit(s, maxw, start=40, w="Bold"):
    z = start
    while font(w, z).getlength(s) > maxw and z > 20: z -= 2
    return font(w, z)

def tag(img, s, y, color=GOLD):
    f = font("Bold", 36); w = f.getlength(s) + 52; x = CX - w / 2
    rrect(img, [x, y, x + w, y + 66], 33, color + (255,)); txt(img, s, x + 26, y + 12, f, BG2)

def swipe(img, label="Swipe"):
    f = font("Bold", 40); s = f"{label}  →"; w = f.getlength(s) + 60
    rrect(img, [CX - w / 2, 1330, CX + w / 2, 1410], 40, (255, 255, 255, 30)); ctr(img, s, CX, 1370, f, WHITE)

def follow_box(img, line, y=1290):
    rrect(img, [90, y, 910, y + 150], 30, GOLD + (255,))
    ctr(img, "Abonne-toi", CX, y + 50, font("Black", 50), BG2)
    ctr(img, line, CX, y + 106, fit(line, 760, 34, "SemiBold"), BG2)

BASE = Image.new("RGBA", (W, H), BG1)
_d = ImageDraw.Draw(BASE)
for _y in range(0, H, 8):
    _k = _y / H; _d.rectangle([0, _y, W, _y + 8], fill=tuple(int(BG1[i] * (1 - _k) + BG2[i] * _k) for i in range(3)) + (255,))
def new(): return BASE.copy()

def cover(spec, swipe_label="Swipe"):
    c = spec["cover"]; s = new(); tag(s, c.get("tag", "FOOT"), 380, col(c.get("tag_color")))
    y = 500
    if c.get("big"):
        f = fitsize(c["big"], "Black", 250, 820, 120)
        y = ctext(s, c["big"], y, f, col(c.get("big_color")), spacing=1.0) + 10
        if c.get("big2"): y = ctext(s, c["big2"], y, font("Black", 110), WHITE, spacing=1.0) + 20
    if c.get("title"):
        tf = fitsize(c["title"], "Black", 72 if c.get("big") else 96, 830, 56)
        while tf.size > 48 and y + 10 + int(tf.size * 1.16) * len(wrap(c["title"], tf, 830)) > 1150: tf = font("Black", tf.size - 4)
        y = ctext(s, c["title"], y + 10, tf, WHITE) + 30
    if c.get("sub") and y < 1180: y = ctext(s, c["sub"], y + 10, font("SemiBold", 52), GOLD) + 20
    if c.get("note") and y < 1180: ctext(s, c["note"], y + 20, font("Medium", 44), MUTED)
    swipe(s, c.get("swipe", swipe_label)); return s

def end_slide(spec, title, sub, extra=None):
    s = new(); y = ctext(s, title, 400, fitsize(title, "Black", 130, 830, 80), WHITE)
    y = ctext(s, sub, y + 40, font("SemiBold", 56), GOLD)
    if extra: extra(s, y + 60)
    follow_box(s, spec.get("follow", "un nouveau post foot chaque jour")); return s

# ---------- formats ----------
def f_quiz(spec):
    out = [cover(spec, "Indice 1")]
    clues = spec["clues"]; heads = spec.get("clue_heads", ["Facile ? Pas sûr.", "Ça se resserre…", "Dernière chance."])
    prompts = spec.get("clue_prompts", ["Tu as une idée ?", "Toujours pas ?", "Écris ta réponse avant de swiper."])
    for i in range(len(clues)):
        s = new(); tag(s, f"INDICE {i + 1}/{len(clues)}", 330)
        ctext(s, heads[i % len(heads)], 450, font("ExtraBold", 70), WHITE)
        ctext(s, prompts[i % len(prompts)], 620, font("Bold", 44), GOLD)
        y = 760
        for j, c in enumerate(clues[:i + 1]):
            active = j == i; h = 210
            rrect(s, [90, y, 910, y + h], 28, (255, 255, 255, 40 if active else 16))
            circ(s, 160, y + h / 2, 40, fill=(GOLD if active else MUTED) + (255,)); ctr(s, str(j + 1), 160, y + h / 2, font("Black", 40), BG2)
            ltext(s, c, 230, y + 38, fit_body(c, 650, 40), WHITE if active else MUTED, maxw=650)
            y += h + 24
        out.append(s)
    a = spec["answer"]; s = new(); tag(s, "RÉPONSE", 330)
    y = ctext(s, a["first"], 450, fitsize(a["first"], "Black", 130, 830, 80), WHITE, spacing=1.0)
    y = ctext(s, a["last"], y, fitsize(a["last"], "Black", 150, 830, 90), GOLD, spacing=1.0)
    y = ctext(s, a.get("note", ""), y + 40, font("SemiBold", 46), MUTED)
    ctext(s, spec.get("question", "Tu l'as trouvé à quel indice ?"), max(y + 80, 1060), font("ExtraBold", 58), WHITE)
    follow_box(s, spec.get("follow", "un nouveau quiz foot chaque jour")); out.append(s)
    return out

def fit_body(s, maxw, start):  # keep clue text within 3 lines
    z = start
    while z > 30 and len(wrap(s, font("SemiBold", z), maxw)) > 3: z -= 2
    return font("SemiBold", z)

def f_vote(spec):
    out = [cover(spec)]; cands = spec["candidates"]
    for k, c in enumerate(cands, 1):
        color = col(c.get("color")); s = new(); tag(s, f"CANDIDAT {k}/{len(cands)}", 330, color)
        y = ctext(s, c["name"], 440, fitsize(c["name"], "Black", 170, 830, 90), color, spacing=1.0)
        y = ctext(s, c.get("sub", ""), y + 20, font("Bold", 52), WHITE)
        pl = c.get("players") or []
        if pl:
            n = len(pl); gapx = 820 / n; cy = max(y + 170, 900)
            for i, p in enumerate(pl):
                x = 90 + gapx * (i + 0.5); r = 100 if n <= 3 else 80
                circ(s, x, cy, r, fill=color + (255,)); ctr(s, p[0], x, cy, font("Black", int(r * 0.92)), BG2)
                ctr(s, p, x, cy + r + 45, fit(p, gapx - 20, 44), WHITE)
            y = cy + 200
        lines = c.get("facts") or []
        for fct in lines:
            fh = 60 + 58 * len(wrap(fct, font("SemiBold", 46), 760))
            rrect(s, [90, y, 910, y + fh], 28, (255, 255, 255, 30)); ctext(s, fct, y + 30, font("SemiBold", 46), WHITE, maxw=760)
            y += fh + 20
        out.append(s)
    def chips(s, y):
        n = len(cands); w = min(260, 800 / n - 20)
        for i, c in enumerate(cands):
            x = 90 + (820 / n) * (i + 0.5)
            rrect(s, [x - w / 2, y, x + w / 2, y + 170], 30, col(c.get("color")) + (255,))
            ctr(s, c.get("short", c["name"]), x, y + 85, fit(c.get("short", c["name"]), w - 24, 70, "Black"), BG2)
        if spec.get("end_note"): ctext(s, spec["end_note"], y + 230, font("Medium", 44), MUTED)
    out.append(end_slide(spec, spec.get("end_title", "Ton vote ?"), spec.get("end_sub", "Réponds en un mot en commentaire"), chips))
    return out

def f_story(spec):
    out = [cover(spec, spec["cover"].get("swipe", "L'histoire"))]
    for sl in spec["slides"]:
        s = new(); color = col(sl.get("color")); tag(s, sl.get("tag", ""), 330, color)
        y = ctext(s, sl["big"], 460, fitsize(sl["big"], "Black", sl.get("size", 100), 830, 64), color if sl.get("color") != "red" else WHITE)
        if sl.get("body"): y = ctext(s, sl["body"], y + 50, font("SemiBold", 52), MUTED)
        for p in sl.get("points", []):
            h = 60 + 52 * len(wrap(p, font("SemiBold", 42), 740))
            rrect(s, [90, y + 30, 910, y + 30 + h], 28, (255, 255, 255, 30)); ltext(s, p, 130, y + 58, font("SemiBold", 42), WHITE, maxw=740)
            y += h + 24
        out.append(s)
    out.append(end_slide(spec, spec.get("end_title", "Et toi ?"), spec.get("end_sub", "Dis-le en commentaire.")))
    return out

def f_top(spec):
    out = [cover(spec, "Le top")]
    items = spec["items"]
    for i, it in enumerate(items):
        s = new(); rank = len(items) - i if spec.get("countdown", True) else i + 1
        ctr(s, f"#{rank}", CX, 470, font("Black", 200), GOLD)
        y = ctext(s, it["title"], 620, fitsize(it["title"], "Black", 90, 830, 60), WHITE)
        if it.get("big"):
            bf = font("Black", 140)
            while bf.size > 56 and bf.getlength(it["big"]) > 830: bf = font("Black", bf.size - 4)
            y = ctext(s, it["big"], y + 30, bf, GOLD, spacing=1.0)
        if it.get("body"): ctext(s, it["body"], y + 40, font("SemiBold", 50), MUTED)
        out.append(s)
    out.append(end_slide(spec, spec.get("end_title", "Lequel tombera en premier ?"), spec.get("end_sub", "Dis-le en commentaire.")))
    return out

# budget: pitch with three slots
PITCH = Image.new("RGBA", (W, H), (0, 0, 0, 0))
_p = ImageDraw.Draw(PITCH)
_p.rounded_rectangle([110, 520, 890, 1180], 26, fill=(20, 78, 50, 240))
_lc = (255, 255, 255, 110)
_p.rectangle([130, 540, 870, 1160], outline=_lc, width=4); _p.rectangle([300, 540, 700, 690], outline=_lc, width=4)
_p.rectangle([410, 540, 590, 595], outline=_lc, width=4); _p.arc([410, 1070, 590, 1250], 180, 360, fill=_lc, width=4)
SLOTS = [(270, 870), (500, 770), (730, 870)]
TIER_COLORS = [COLORS["gold"], COLORS["violet"], COLORS["teal"]]

def f_budget(spec):
    tiers = spec["tiers"]; total = spec["budget"]; unit = spec.get("unit", "M")
    price = {n: t["price"] for t in tiers for n in t["names"]}
    tcol = {n: TIER_COLORS[i % 3] for i, t in enumerate(tiers) for n in t["names"]}
    sub = spec.get("subs", {})
    def slot(s, i, name=None, crossed=False):
        cx, cy = SLOTS[i]
        if name is None:
            circ(s, cx, cy, 74, fill=(255, 255, 255, 18), outline=(255, 255, 255, 120), width=4); ctr(s, "?", cx, cy, font("Black", 64), (255, 255, 255, 140))
            if crossed:
                L = Image.new("RGBA", (200, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
                d.line([(40, 40), (160, 160)], fill=RED + (255,), width=14); d.line([(160, 40), (40, 160)], fill=RED + (255,), width=14)
                s.alpha_composite(L, (cx - 100, cy - 100))
            return
        circ(s, cx, cy, 78, fill=tcol[name] + (255,), outline=(255, 255, 255, 255), width=4)
        ctr(s, f"{price[name]}{unit}", cx, cy, font("Black", 46), BG2); ctr(s, name, cx, cy + 118, fit(name, 230, 40), WHITE)
        if name in sub: ctr(s, sub[name], cx, cy + 162, font("Medium", 26), MUTED)
    def bar(s, spent, color, label=None, y=1250):
        rrect(s, [110, y, 890, y + 36], 18, (255, 255, 255, 34)); rrect(s, [110, y, 110 + 780 * min(1, spent / total), y + 36], 18, color + (255,))
        txt(s, "Budget", 110, y - 56, font("Medium", 34), MUTED)
        l = label or f"{spent}{unit} / {total}{unit}"; fb = font("Bold", 34); txt(s, l, 890 - fb.getlength(l), y - 56, fb, WHITE)
    out = []
    s = new(); tag(s, spec.get("tag", "DÉFI DU JOUR"), 380); ctr(s, f"{total}{unit}", CX, 640, font("Black", 260), GOLD)
    ctext(s, spec["title"], 800, font("ExtraBold", 72), WHITE); ctext(s, spec.get("rule", "3 joueurs. Pas un de plus."), 920, font("SemiBold", 52), MUTED)
    for x, _ in SLOTS: pass
    for x in (270, 500, 730):
        circ(s, x, 1130, 70, fill=(255, 255, 255, 18), outline=(255, 255, 255, 140), width=4); ctr(s, "?", x, 1130, font("Black", 60), (255, 255, 255, 150))
    swipe(s, "Voir le marché"); out.append(s)
    s = new(); tag(s, "LE MARCHÉ", 300); ctext(s, f"Max {total}{unit} · 3 joueurs", 390, font("Bold", 52), WHITE)
    for r, t in enumerate(tiers):
        ry = 470 + r * 300; c = TIER_COLORS[r % 3]
        circ(s, 128, ry + 120, 66, fill=c + (255,)); ctr(s, f"{t['price']}{unit}", 128, ry + 120, font("Black", 42), BG2)
        for j, n in enumerate(t["names"][:3]):
            x = 216 + j * 244; y = ry + 45
            rrect(s, [x, y, x + 232, y + 150], 22, (255, 255, 255, 36)); rrect(s, [x, y + 18, x + 10, y + 132], 5, c + (255,))
            f = fit(n, 202, 40)
            if n in sub: ctr(s, n, x + 120, y + 58, f, WHITE); ctr(s, sub[n], x + 120, y + 104, font("Medium", 24), MUTED)
            else: ctr(s, n, x + 120, y + 75, f, WHITE)
    out.append(s)
    if spec.get("trap"):
        a, b = spec["trap"]; s = new(); tag(s, "PIÈGE N°1", 300, RED); ctext(s, f"{a} + {b} ?", 390, font("ExtraBold", 66), WHITE)
        s.alpha_composite(PITCH); slot(s, 0, a); slot(s, 2, b); slot(s, 1, None, crossed=True)
        bar(s, price[a] + price[b], RED); ctext(s, "Plus rien pour le 3e joueur.", 1330, font("Bold", 48), RED); out.append(s)
    pick = spec["pick"]; s = new(); tag(s, "MON CHOIX", 300)
    ctr(s, spec.get("pick_title", "Mon trio"), CX, 440, fit(spec.get("pick_title", "Mon trio"), 830, 112, "Black"), GOLD)
    s.alpha_composite(PITCH)
    for i, n in enumerate(pick): slot(s, i, n)
    sp = sum(price[n] for n in pick); bar(s, sp, GOLD if sp == total else COLORS["teal"], f"{sp}{unit} pile" if sp == total else None)
    ctext(s, " · ".join(pick), 1330, font("Bold", 48), WHITE); out.append(s)
    def recap(s, y):
        ex = spec.get("example")
        if ex:
            f = font("Medium", 40); t = "ex : " + ex; w = f.getlength(t) + 60
            rrect(s, [CX - w / 2, y, CX + w / 2, y + 80], 40, (255, 255, 255, 30)); ctr(s, t, CX, y + 40, f, WHITE); y += 140
        for i, t in enumerate(tiers):
            yy = y + i * 100; c = TIER_COLORS[i % 3]
            circ(s, 160, yy + 30, 42, fill=c + (255,)); ctr(s, f"{t['price']}{unit}", 160, yy + 30, font("Black", 30), BG2)
            txt(s, " · ".join(t["names"]), 230, yy + 6, fit(" · ".join(t["names"]), 680, 40, "Medium"), MUTED)
    out.append(end_slide(spec, "Et toi ?", spec.get("end_sub", "Écris ton trio en commentaire"), recap))
    return out

FORMATS = {"quiz": f_quiz, "vote": f_vote, "story": f_story, "top": f_top, "budget": f_budget}

def render(spec, outdir):
    os.makedirs(outdir, exist_ok=True)
    slides = FORMATS[spec["format"]](spec)
    for i, im in enumerate(slides, 1): im.convert("RGB").save(os.path.join(outdir, f"{i:02d}.jpg"), quality=92)
    with open(os.path.join(outdir, "caption.txt"), "w") as f: f.write(spec["caption"].strip() + "\n")
    return len(slides)

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    print(render(spec, sys.argv[2]), "slides")
