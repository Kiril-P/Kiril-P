"""Draw a year of GitHub activity as an SVG card in the same terminal style as the duck.

    python3 assets/stats.py > assets/stats.svg

Contributions come from the public contribution calendar (what anyone sees on the
profile; private work appears there only as anonymous counts). Languages come from
public, non-fork repos. Standard library only. If GITHUB_TOKEN is set it's used for
the languages API, otherwise requests are anonymous. Runs daily from
.github/workflows/stats.yml.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

USER = "Kiril-P"
MARKERS = [(dt.date(2026, 6, 1), "naiss ride + easeaccess24")]   # moments worth pointing at
SKIP_LANGS = {"HTML", "CSS", "SCSS", "Jupyter Notebook", "Dockerfile", "Makefile", "Shell"}


# ---------------------------------------------------------------- data
def get(url, api=False):
    h = {"User-Agent": "stats-svg"}
    if api and os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30).read().decode()


def calendar():
    page = get(f"https://github.com/users/{USER}/contributions")
    days = {}
    for tag in re.findall(r"<td\b[^>]*>", page):
        date, cid = (re.search(rf'{a}="([^"]+)"', tag) for a in ("data-date", "id"))
        if date and cid:
            days[cid.group(1)] = [dt.date.fromisoformat(date.group(1)), 0]
    for cid, label in re.findall(r'<tool-tip\b[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        n = re.match(r"([\d,]+) contribution", label)
        if cid in days and n:
            days[cid][1] = int(n.group(1).replace(",", ""))
    if len(days) < 300:
        sys.exit(f"parsed only {len(days)} days; GitHub's markup probably changed. Not overwriting.")
    return sorted(tuple(v) for v in days.values())


def languages():
    repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", api=True))
    total = {}
    for r in repos:
        if r.get("fork"):
            continue
        for lang, n in json.loads(get(r["languages_url"], api=True)).items():
            if lang not in SKIP_LANGS:
                total[lang] = total.get(lang, 0) + n
    s = sum(total.values()) or 1
    top = sorted(total.items(), key=lambda kv: -kv[1])[:5]
    return [(k.lower(), v / s) for k, v in top]


def streaks(counts):
    best = run = 0
    for n in counts:
        run = run + 1 if n else 0
        best = max(best, run)
    cur, i = 0, len(counts) - 1
    if counts[i] == 0:              # today isn't over yet
        i -= 1
    while i >= 0 and counts[i]:
        cur, i = cur + 1, i - 1
    return cur, best


# ---------------------------------------------------------------- drawing
def smooth(pts):
    """Catmull-Rom through pts, as an SVG cubic path (no leading M)."""
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return " ".join(out)


def nice_step(top):
    for step in (50, 100, 200, 250, 500, 1000, 2000, 2500, 5000):
        if top / step <= 5:
            return step
    return 10000


def svg(days, langs):
    counts = [n for _, n in days]
    total, active = sum(counts), sum(1 for n in counts if n)
    cur, best = streaks(counts)
    peak_day, peak = max(days, key=lambda d: d[1])

    W, bar, pad = 720, 30, 26
    x0, x1, y0, y1 = 86, W - 40, bar + 70, bar + 280          # plot box (y0 top, y1 baseline)
    H = bar + 520

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="{total} GitHub contributions in the last year: cumulative chart, top languages and streaks">',
         "<style>",
         ":root{--bg:#fbfaf7;--line:#d0d7de;--ink:#9a6700;--hot:#d1530f;--dim:#6e7781;--text:#24292f;--grid:#d0d7de}",
         "@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--line:#30363d;--ink:#f2cc60;"
         "--hot:#ff8a4c;--dim:#8b949e;--text:#e6edf3;--grid:#30363d}}",
         "text{font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:var(--text);white-space:pre}",
         ".t{fill:var(--dim);font-size:11px}.h{fill:var(--hot);font-size:11px;letter-spacing:.08em}",
         ".k{fill:var(--ink)}.dm{fill:var(--dim)}.big{font-size:22px;fill:var(--ink)}",
         ".grid{stroke:var(--grid);stroke-dasharray:2 4}.ax{stroke:var(--dim);stroke-width:.7;opacity:.6}",
         ".curve{fill:none;stroke:var(--ink);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}",
         ".s0{stop-color:var(--ink);stop-opacity:.45}.s1{stop-color:var(--ink);stop-opacity:0}",
         ".mk{stroke:var(--hot);stroke-dasharray:3 3}",
         ".pulse{fill:var(--hot);transform-box:fill-box;transform-origin:center;animation:p 2s ease-out infinite}",
         "@keyframes p{0%{transform:scale(1);opacity:.7}100%{transform:scale(4);opacity:0}}",
         ".cur{fill:var(--ink);animation:b 1.1s step-end infinite}@keyframes b{50%{opacity:0}}",
         "</style>",
         '<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
         '<stop class="s0" offset="0"/><stop class="s1" offset="1"/></linearGradient></defs>',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="var(--bg)" stroke="var(--line)"/>',
         f'<path d="M.5 {bar}H{W - .5}" stroke="var(--line)"/>']
    for k, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        o.append(f'<circle cx="{18 + 16 * k}" cy="{bar / 2}" r="5" fill="{col}"/>')
    o.append(f'<text class="t" x="{W / 2}" y="{bar / 2 + 4}" text-anchor="middle">~/kiril — stats.py</text>')

    # ---- cumulative chart
    o.append(f'<text class="h" x="{pad}" y="{bar + 34}">$ contributions --cumulative --last 12 months</text>')
    start, end = days[0][0], days[-1][0]
    span = (end - start).days or 1
    run, cum = 0, []
    for d, n in days:
        run += n
        cum.append((d, run))
    step = nice_step(total)
    top = max(step, -(-total // step) * step)
    X = lambda d: x0 + (d - start).days / span * (x1 - x0)
    Y = lambda v: y1 - v / top * (y1 - y0)
    for v in range(0, top + 1, step):
        if v:
            o.append(f'<line class="grid" x1="{x0}" y1="{Y(v):.1f}" x2="{x1}" y2="{Y(v):.1f}"/>')
        o.append(f'<text class="t" x="{x0 - 10}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:,}</text>')
    pts = [(X(d), Y(v)) for i, (d, v) in enumerate(cum) if i % 7 == 0 or i == len(cum) - 1]
    path = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} " + smooth(pts)
    o.append(f'<path d="{path} L{pts[-1][0]:.1f},{y1} L{pts[0][0]:.1f},{y1}Z" fill="url(#fade)"/>')
    o.append(f'<path class="curve" d="{path}"/>')
    o.append(f'<line class="ax" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    d = dt.date(start.year, start.month, 1)
    while d <= end:
        if d >= start:
            o.append(f'<line class="ax" x1="{X(d):.1f}" y1="{y1}" x2="{X(d):.1f}" y2="{y1 + 4}"/>')
            o.append(f'<text class="t" x="{X(d):.1f}" y="{y1 + 18}" text-anchor="middle">{d:%b}'.lower() + "</text>")
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    for md, label in MARKERS:
        if start < md < end:
            o.append(f'<line class="mk" x1="{X(md):.1f}" y1="{y0 - 6}" x2="{X(md):.1f}" y2="{y1}"/>')
            o.append(f'<text class="h" x="{X(md) - 6:.1f}" y="{y0 + 4}" text-anchor="end">{label} →</text>')
    ex, ey = pts[-1]
    o.append(f'<circle class="pulse" cx="{ex:.1f}" cy="{ey:.1f}" r="3.5"/>')
    o.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="var(--hot)"/>')

    # ---- languages (ASCII bars) and numbers
    ly = bar + 350
    o.append(f'<text class="h" x="{pad}" y="{ly}">$ top languages --public</text>')
    width = 18
    for i, (lang, share) in enumerate(langs):
        filled = max(1, round(share * width))
        y = ly + 30 + i * 24
        o.append(f'<text x="{pad}" y="{y}">{lang[:12]}</text>')
        o.append(f'<text x="{pad + 108}" y="{y}"><tspan class="k">{"#" * filled}</tspan>'
                 f'<tspan class="dm">{"." * (width - filled)}</tspan></text>')
        o.append(f'<text class="t" x="{pad + 108 + width * 7.25 + 10:.0f}" y="{y}">{share:.0%}</text>')

    nx = 420
    o.append(f'<text class="h" x="{nx}" y="{ly}">$ numbers</text>')
    facts = [(f"{total:,}", "contributions this year"), (f"{active}", "days with a commit"),
             (f"{best}d", f"longest streak · now {cur}d"), (f"{peak}", f"on {peak_day:%b %-d}, the busiest day")]
    for i, (big, small) in enumerate(facts):
        y = ly + 34 + i * 29
        o.append(f'<text x="{nx}" y="{y}"><tspan class="big">{big}</tspan>'
                 f'<tspan class="t" dx="10">{small}</tspan></text>')

    o.append(f'<text class="t" x="{W - pad}" y="{H - 18}" text-anchor="end">'
             f'updated {dt.date.today():%Y-%m-%d}<tspan class="cur"> ▋</tspan></text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    print(svg(calendar(), languages()))
