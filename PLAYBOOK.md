# Playbook: football TikTok account

Goal: grow the account to 10k followers with photo carousels that make people **comment, share and follow**.
Language: French. Audience: French-speaking football fans.

## The pipeline
1. A post is a JSON spec in `content/specs/` (see formats below).
2. `python3 tools/render.py content/specs/NAME.json outbox/NAME` renders 1080x1920 JPG slides + `caption.txt`.
3. Push to `main`. The site serves the photos; the **Send to TikTok inbox** workflow sends **one** post from
   `outbox/` (oldest name first) to the TikTok inbox as a draft, three times a day. Louis adds a trending sound and publishes.
4. Sent items are removed from `outbox/` and logged in `state/sent.log`. Used specs move to `content/used/`.

Queue rules: keep `outbox/` between **6 and 12** posts. Never dump more than that: TikTok limits unfinished drafts.
Folder names start with the date and a number so they send in order: `2026-10-24-01-quiz-zidane`.
Alternate formats; never two of the same format in a row.

## Content rules (non-negotiable)
- **Every fact must be true and checkable.** Verify anything not rock-solid with a web search before writing it.
  Prefer history and records over fresh news. No invented quotes. No rumours presented as facts.
- **No photos, logos, club crests or match footage**: text and drawn graphics only (copyright).
- Quizzes: the caption and hashtags must **not** reveal the answer.
- Each post ends on the follow slide (`follow` = what they get by following, e.g. "un nouveau quiz foot chaque jour").
- Hooks: a number, a question or a challenge on slide 1. End with a question that is easy to answer in one word.
- No politics, no insults, nothing about players' private lives. Debates stay about football.
- Caption: one punchy line + 5-8 hashtags, always including `#football #foot #footballtiktok #pourtoi`.

## Formats (spec["format"])
Common keys: `caption` (required), `follow`.

**quiz**: guess the player/club in 3 clues, hardest first.
`cover {tag,title,sub,note}`, `clues [3 strings, <= ~110 chars]`, `answer {first,last,note}`, optional `question`.

**vote**: 2-3 candidates, the audience votes.
`cover {tag,title,sub}`, `candidates [{name, short, color, sub, players?[], facts[1-2]}]`, `end_sub`, `end_note`.
Colors: gold, violet, teal, red, blue, orange.

**story**: a crazy true story in 3-4 slides.
`cover {tag, big, big2?, big_color?, title, swipe}`, `slides [{tag, big, body? , points?[], color?, size?}]`,
`end_title`, `end_sub`.

**top**: countdown list (5 items, #5 first).
`cover {tag,title,sub}`, `items [{title, big, body}]`, `end_title`, `end_sub`.

**budget**: "compose ton trio" with a budget.
`budget` (int), `title`, `tiers [{price, names[3 max]}] x3`, `trap [2 names that use the whole budget]`,
`pick [3 names, sum = budget]`, `pick_title`, `example`, `end_sub`, optional `subs {name: small text}`.

## Idea bank (to pick from, check facts first)
- quiz: Zidane, Ronaldinho, Ribéry, Benzema, Cantona, Papin, Kaká, Pirlo, Ibrahimović, Griezmann, a club ("devine le club")
- vote: best GK ever, best Ligue 1 player of the 2000s, best free kick taker, Ballon d'Or "voleurs", Messi vs Ronaldo stats duel
- story: Denmark Euro 92, Porto 2004, Calais 2000 (CFA team in the Coupe de France final), Zidane headbutt 2006 final, Chelsea 2012
- top: biggest comebacks, youngest scorers in World Cup, most expensive transfers (check figures), fastest goals
- budget: defence (12M), "attaque Ligue 1", "XI de légendes" variants
- Match days (Tue/Wed Champions League, weekends): results/line-ups posts the same evening, facts from official sources only.
