"""Draw the last year of GitHub contributions as an ASCII heatmap SVG.

    python3 assets/stats.py > assets/stats.svg

Reads the public contribution calendar (github.com/users/<user>/contributions),
the same data anyone sees on the profile, so it needs no token and can't leak
anything private. Standard library only. Runs daily from .github/workflows/stats.yml.
"""
import datetime as dt
import html
import re
import sys
import urllib.request

USER = "Kiril-P"
GLYPHS = "·:+#@"                 # GitHub's levels 0..4
CW, LH = 7.8, 13.0


def fetch():
    req = urllib.request.Request(f"https://github.com/users/{USER}/contributions",
                                 headers={"User-Agent": "stats-svg"})
    page = urllib.request.urlopen(req, timeout=30).read().decode()
    days = {}
    for m in re.finditer(r'<td\b[^>]*>', page):
        tag = m.group(0)
        date, cid, lvl = (re.search(rf'{a}="([^"]+)"', tag) for a in ("data-date", "id", "data-level"))
        if date and cid and lvl:
            days[cid.group(1)] = [dt.date.fromisoformat(date.group(1)), int(lvl.group(1)), 0]
    for cid, label in re.findall(r'<tool-tip\b[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        n = re.match(r"([\d,]+) contribution", label)
        if cid in days and n:
            days[cid][2] = int(n.group(1).replace(",", ""))
    if len(days) < 300:
        sys.exit(f"parsed only {len(days)} days; GitHub's markup probably changed. Not overwriting.")
    return sorted((d, lvl, n) for d, lvl, n in days.values())


def streaks(days):
    counts = [n for _, _, n in days]
    best = run = 0
    for n in counts:
        run = run + 1 if n else 0
        best = max(best, run)
    cur, i = 0, len(counts) - 1
    if counts[i] == 0:              # today not done yet: count from yesterday
        i -= 1
    while i >= 0 and counts[i]:
        cur, i = cur + 1, i - 1
    return cur, best


def svg(days):
    total = sum(n for *_, n in days)
    active = sum(1 for *_, n in days if n)
    cur, best = streaks(days)
    peak = max(days, key=lambda d: d[2])

    first = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)   # back to Sunday
    weeks = (days[-1][0] - first).days // 7 + 1

    pad, bar, label = 22, 30, 4                     # label = columns reserved for weekday names
    gx, gy = pad + label * CW, bar + pad + LH * 1.6  # grid origin
    W = int(gx + weeks * CW + pad)
    H = int(gy + 7 * LH + LH * 5.6 + pad)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="{total} GitHub contributions in the last year, drawn as an ASCII heatmap">',
         "<style>",
         ":root{--bg:#fbfaf7;--line:#d0d7de;--ink:#9a6700;--hot:#d1530f;--dim:#6e7781;--text:#24292f}",
         "@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--line:#30363d;--ink:#f2cc60;"
         "--hot:#ff8a4c;--dim:#8b949e;--text:#e6edf3}}",
         "text{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}",
         ".t{fill:var(--dim);font-size:11px}.x{fill:var(--text)}.k{fill:var(--ink)}",
         ".l0{fill:var(--dim);opacity:.45}.l1{fill:var(--ink);opacity:.55}.l2{fill:var(--ink);opacity:.8}"
         ".l3{fill:var(--ink)}.l4{fill:var(--hot)}",
         ".c{fill:var(--ink);animation:b 1.1s step-end infinite}@keyframes b{50%{opacity:0}}",
         "</style>",
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="var(--bg)" stroke="var(--line)"/>',
         f'<path d="M.5 {bar}H{W - .5}" stroke="var(--line)"/>']
    for k, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        o.append(f'<circle cx="{18 + 16 * k}" cy="{bar / 2}" r="5" fill="{col}"/>')
    o.append(f'<text class="t" x="{W / 2}" y="{bar / 2 + 4}" text-anchor="middle">~/kiril — git log --since="1 year ago"</text>')

    # month labels, placed over the first week that starts in that month
    seen = set()
    for w in range(weeks):
        d = first + dt.timedelta(weeks=w)
        if d.day <= 7 and d.month not in seen and w < weeks - 2:
            seen.add(d.month)
            o.append(f'<text class="t" x="{gx + w * CW:.1f}" y="{gy - LH * 0.6:.1f}">{d.strftime("%b").lower()}</text>')
    for r, name in ((1, "mon"), (3, "wed"), (5, "fri")):
        o.append(f'<text class="t" x="{pad}" y="{gy + (r + 1) * LH - 3:.1f}">{name}</text>')

    for d, lvl, n in days:
        w, r = (d - first).days // 7, (d.weekday() + 1) % 7
        tip = f"{n} contribution{'s' * (n != 1)} on {d:%b %-d}"
        o.append(f'<text class="l{lvl}" x="{gx + w * CW:.1f}" y="{gy + (r + 1) * LH:.1f}">'
                 f'<title>{tip}</title>{GLYPHS[lvl]}</text>')

    y = gy + 7 * LH + LH * 1.9
    line = [("x", f"{total:,}"), ("t", " contributions · "), ("x", f"{active}"), ("t", " active days · busiest "),
            ("k", f"{peak[0]:%b %-d}"), ("t", f" ({peak[2]})")]
    line2 = [("t", "streak "), ("x", f"{cur} day{'s' * (cur != 1)}"), ("t", " · best "), ("x", f"{best} days")]
    line3 = [("t", "less "), ("l0", GLYPHS[0]), ("l1", GLYPHS[1]), ("l2", GLYPHS[2]), ("l3", GLYPHS[3]),
             ("l4", GLYPHS[4]), ("t", " more")]
    for row, parts in ((0, line), (1, line2), (2, line3)):
        spans = "".join(f'<tspan class="{c}">{html.escape(s)}</tspan>' for c, s in parts)
        o.append(f'<text x="{pad}" y="{y + row * LH * 1.35:.1f}">{spans}</text>')
    stamp = f"updated {dt.date.today():%Y-%m-%d}"
    o.append(f'<text class="t" x="{W - pad}" y="{y + 2 * LH * 1.35:.1f}" text-anchor="end">{stamp}<tspan class="c"> ▋</tspan></text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    print(svg(fetch()))
