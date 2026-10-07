"""A rubber duck, spinning and bobbing on ASCII water, as an animated SVG.

    python3 assets/duck.py > assets/duck.svg

The duck is a signed-distance field, raymarched from a camera that orbits it,
shaded into characters. Each frame is a group of <text> runs; CSS flips which
group is visible, so it animates inside a GitHub README with no JavaScript.
"""
import numpy as np

COLS, ROWS, FRAMES, SECONDS = 50, 20, 48, 7.2
SHADES = " .:-=+*#%@"
CW, LH = 7.8, 13.0          # character cell (px)
WATER_ROWS = 4

V = lambda *x: np.array(x, dtype=float)


# ---------------------------------------------------------------- shapes
def ellipsoid(p, c, r):
    q = (p - c) / r
    k0 = np.linalg.norm(q, axis=-1)
    k1 = np.linalg.norm(q / r, axis=-1)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def ball(p, c, r):
    return np.linalg.norm(p - c, axis=-1) - r


def tapered(p, a, b, r0, r1):
    ab = b - a
    h = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - a - ab * h[..., None], axis=-1) - (r0 + (r1 - r0) * h)


def blend(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * h - k * h * (1 - h)


# ---------------------------------------------------------------- the duck
BEAK = (V(0, 1.1, 0.62), V(0.17, 0.065, 0.2))


def duck(p):
    """Distance to the duck, and whether the nearest surface is the beak."""
    body = ellipsoid(p, V(0, 0.42, -0.04), V(0.5, 0.37, 0.64))
    body = blend(body, tapered(p, V(0, 0.48, -0.5), V(0, 0.82, -0.8), 0.2, 0.03), 0.12)   # tail
    for s in (-1, 1):
        body = blend(body, ellipsoid(p, V(0.43 * s, 0.5, -0.1), V(0.1, 0.17, 0.32)), 0.06)  # wings
    head = ball(p, V(0, 1.14, 0.27), 0.29)
    for s in (-1, 1):
        head = np.maximum(head, -ball(p, V(0.14 * s, 1.22, 0.52), 0.055))                  # eyes
    body = blend(body, tapered(p, V(0, 0.68, 0.18), V(0, 1.02, 0.25), 0.22, 0.17), 0.1)  # neck
    body = blend(body, head, 0.09)
    beak = ellipsoid(p, *BEAK)
    return np.minimum(body, beak), beak < body


def normal(f, p, e=1e-3):
    g = np.stack([f(p + o)[0] - f(p - o)[0] for o in np.eye(3) * e], -1)
    return g / np.maximum(np.linalg.norm(g, axis=-1, keepdims=True), 1e-9)


def frame(i):
    """Character grid + beak mask for frame i."""
    phase = 2 * np.pi * i / FRAMES
    bob = 0.05 * np.sin(2 * phase)                       # bobs twice per turn
    roll = 0.06 * np.sin(2 * phase + 1.0)

    def scene(p):
        q = p.copy()
        q[..., 1] -= bob
        c, s = np.cos(roll), np.sin(roll)                # small roll around the forward axis
        x, y = q[..., 0].copy(), q[..., 1] - 0.4
        q[..., 0], q[..., 1] = c * x - s * y, s * x + c * y + 0.4
        d, is_beak = duck(q)
        return np.maximum(d, 0.2 - p[..., 1]), is_beak   # waterline: nothing below y = 0.2

    span, cy = 2.0, 0.86                                 # view width (world units), view centre height
    xs = (np.arange(COLS) + 0.5 - COLS / 2) / COLS * span
    ys = cy - (np.arange(ROWS) + 0.5 - ROWS / 2) / ROWS * span * (ROWS * LH) / (COLS * CW)
    X, Y = np.meshgrid(xs, ys)
    c, s = np.cos(phase), np.sin(phase)
    tilt = 0.32
    fwd = V(-s * np.cos(tilt), -np.sin(tilt), -c * np.cos(tilt))
    right = V(c, 0, -s)
    up = np.cross(right, fwd)
    origin = X[..., None] * right + (Y[..., None] - cy) * up + V(0, cy, 0) - fwd * 4

    t = np.zeros(X.shape)
    hit = np.zeros(X.shape, bool)
    for _ in range(80):
        d, _ = scene(origin + fwd * t[..., None])
        hit |= d < 1e-3
        t = np.where(hit, t, t + d * 0.9)
    p = origin + fwd * t[..., None]
    n = np.nan_to_num(normal(scene, p))
    _, beak = scene(p)

    key = V(0.55, 0.75, 0.4)
    key /= np.linalg.norm(key)
    key = V(key[0] * c + key[2] * s, key[1], -key[0] * s + key[2] * c)   # light rides with the camera
    lit = np.clip(n @ key, 0, 1)
    edge = (1 - np.abs(n @ fwd)) ** 2.5
    tone = np.clip(0.2 + 0.8 * lit - 0.3 * edge, 0, 1)
    idx = np.where(hit, 1 + np.round(tone * (len(SHADES) - 2)).astype(int), 0)
    chars = np.array(list(SHADES))[idx]
    return chars, hit & beak


def water(i):
    """A few rows of drifting ripples; each row moves at its own speed."""
    rows = []
    for r in range(WATER_ROWS):
        shift = int(i * (r + 1) * 0.5)
        width = COLS - 4 * r
        line = "".join("~" if (x + shift) % (7 + r) in (0, 1) else
                       "-" if (x + shift) % (11 + 2 * r) == 4 else " " for x in range(width))
        rows.append((2 * r, line))
    return rows


# ---------------------------------------------------------------- svg
def runs(chars, mask, want):
    """Contiguous non-space runs where mask == want, as (col, text)."""
    out, start = [], None
    for x in range(len(chars) + 1):
        on = x < len(chars) and chars[x] != " " and mask[x] == want
        if on and start is None:
            start = x
        elif not on and start is not None:
            out.append((start, "".join(chars[start:x])))
            start = None
    return out


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg():
    pad, bar = 22, 30
    W = int(COLS * CW) + 2 * pad
    H = bar + int((ROWS + WATER_ROWS) * LH) + 2 * pad + 18
    ox, oy = pad, bar + pad
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'role="img" aria-label="An ASCII rubber duck spinning on water">',
         "<style>",
         ":root{--bg:#fbfaf7;--line:#d0d7de;--ink:#9a6700;--beak:#d1530f;--sea:#0969da;--dim:#6e7781}",
         "@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--line:#30363d;--ink:#f2cc60;"
         "--beak:#ff8a4c;--sea:#58a6ff;--dim:#8b949e}}",
         "text{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;white-space:pre}",
         ".d{fill:var(--ink)}.b{fill:var(--beak)}.w{fill:var(--sea);opacity:.75}.t{fill:var(--dim);font-size:11px}",
         f"g.f{{visibility:hidden;animation:k {SECONDS}s step-end infinite}}",
         f"@keyframes k{{0%{{visibility:visible}}{100 / FRAMES:.4f}%,100%{{visibility:hidden}}}}",
         "</style>",
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="var(--bg)" stroke="var(--line)"/>',
         f'<path d="M.5 {bar}H{W - .5}" stroke="var(--line)"/>']
    for k, col in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        o.append(f'<circle cx="{18 + 16 * k}" cy="{bar / 2}" r="5" fill="{col}"/>')
    o.append(f'<text class="t" x="{W / 2}" y="{bar / 2 + 4}" text-anchor="middle">~/kiril — duck.py</text>')
    o.append(f'<text class="t" x="{ox}" y="{H - pad + 8}">$ explain the bug to the duck</text>')

    def put(cls, col, row, text):
        o.append(f'<text class="{cls}" x="{ox + col * CW:.1f}" y="{oy + (row + 1) * LH:.1f}" '
                 f'textLength="{len(text) * CW:.1f}" lengthAdjust="spacingAndGlyphs">{esc(text)}</text>')

    for i in range(FRAMES):
        chars, beak = frame(i)
        o.append(f'<g class="f" style="animation-delay:{SECONDS * i / FRAMES:.3f}s">')
        for r in range(ROWS):
            for col, txt in runs(chars[r], beak[r], False):
                put("d", col, r, txt)
            for col, txt in runs(chars[r], beak[r], True):
                put("b", col, r, txt)
        for r, (indent, line) in enumerate(water(i)):
            for col, txt in runs(np.array(list(line)), np.zeros(len(line), bool), False):
                put("w", indent + col, ROWS + r, txt)
        o.append(f'<text class="t" x="{W - pad}" y="{H - pad + 8}" text-anchor="end">'
                 f'frame {i + 1:02d}/{FRAMES}</text>')
        o.append("</g>")
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    print(svg())
