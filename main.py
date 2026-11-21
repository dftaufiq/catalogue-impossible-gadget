#!/usr/bin/env python3
"""AEROCUP - The Anti-Gravity Mug.

A program that renders one catalogue photograph of an impossible gadget:
a ceramic mug that floats in mid-air while its coffee pours UPHILL from
the saucer below into the cup. Pure Python standard library only - the
image is rasterised by hand (spans, gradients, soft shadows, a small
stroke font) and written as a PNG with zlib. No network, no third-party
packages, deterministic.

Run:  python3 main.py
Out:  /output/entry.png  (1024x1024, <= 1 MiB)
"""
import math
import os
import struct
import zlib

W = H = 1024
OUT = "/output/entry.png"

canvas = bytearray(W * H * 3)
_luts = {}


def _lut(val, alpha):
    key = (val, alpha)
    t = _luts.get(key)
    if t is None:
        ia = 1.0 - alpha
        t = bytes(min(255, max(0, int(round(val * alpha + v * ia))))
                  for v in range(256))
        _luts[key] = t
    return t


def span(y, x0, x1, col):
    """Fill a horizontal span of row y with a solid colour (x0/x1 floats)."""
    x0 = int(math.ceil(x0))
    x1 = int(math.floor(x1)) + 1
    if x1 <= x0 or y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W, x1)
    if x1 <= x0:
        return
    n = x1 - x0
    base = (y * W + x0) * 3
    for c in range(3):
        canvas[base + c: base + c + n * 3: 3] = bytes([col[c]]) * n


def aspan(y, x0, x1, col, alpha):
    """Fill a horizontal span with a colour at the given opacity."""
    if alpha <= 0:
        return
    if alpha >= 1.0:
        span(y, x0, x1, col)
        return
    x0 = int(math.ceil(x0))
    x1 = int(math.floor(x1)) + 1
    if x1 <= x0 or y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W, x1)
    if x1 <= x0:
        return
    n = x1 - x0
    base = (y * W + x0) * 3
    for c in range(3):
        seg = bytes(canvas[base + c: base + c + n * 3: 3])
        canvas[base + c: base + c + n * 3: 3] = seg.translate(_lut(col[c], alpha))


def grad_bytes(c0, c1, n):
    if n <= 1:
        return [bytes([c0[c]]) for c in range(3)]
    out = []
    for c in range(3):
        out.append(bytes(int(round(c0[c] + (c1[c] - c0[c]) * i / (n - 1)))
                        for i in range(n)))
    return out


def ellipse(cx, cy, rx, ry, col, alpha=1.0):
    if rx <= 0 or ry <= 0:
        return
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry) + 1)
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / ry
        if abs(dy) >= 1.0:
            continue
        dx = rx * math.sqrt(1.0 - dy * dy)
        if alpha >= 1.0:
            span(y, cx - dx, cx + dx, col)
        else:
            aspan(y, cx - dx, cx + dx, col, alpha)


def disc(cx, cy, r, col, alpha=1.0):
    ellipse(cx, cy, r, r, col, alpha)


def soft_disc(cx, cy, r, col, alpha=1.0):
    """Disc with a feathered edge (halo pass, then solid core)."""
    if r <= 0:
        return
    disc(cx, cy, r * 1.18, col, alpha * 0.32)
    disc(cx, cy, r, col, alpha)


def rrect(x0, y0, x1, y1, r, c_left, c_right):
    """Rounded rect filled with a horizontal gradient."""
    w = x1 - x0
    gb = grad_bytes(c_left, c_right, max(1, w))
    for y in range(int(y0), int(y1)):
        if y < y0 + r:
            dy = (y0 + r) - y - 0.5
            dx = math.sqrt(max(0.0, r * r - dy * dy))
            xa = int(x0 + r - dx)
            xb = int(x1 - r + dx)
        elif y >= y1 - r:
            dy = y - (y1 - r) + 0.5
            dx = math.sqrt(max(0.0, r * r - dy * dy))
            xa = int(x0 + r - dx)
            xb = int(x1 - r + dx)
        else:
            xa = int(x0)
            xb = int(x1)
        xa = max(0, xa)
        xb = min(W, xb)
        if xb <= xa or y < 0 or y >= H:
            continue
        base = (y * W + xa) * 3
        n = xb - xa
        off = xa - int(x0)
        for c in range(3):
            canvas[base + c: base + c + n * 3: 3] = gb[c][off: off + n]


def soft_shadow(cx, cy, rx, ry, col=(52, 44, 36), alpha=0.26, layers=10):
    for i in range(layers, 0, -1):
        f = 1.0 + 0.11 * i
        ellipse(cx, cy, rx * f, ry * f, col, alpha / layers)


def catmull(pts, steps=20):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for j in range(steps):
            t = j / steps
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def tube(pts, w0, w1, col, hi=None):
    """A tapering 3D tube along a point list (stamped soft discs)."""
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        t = i / max(1, n - 1)
        w = w0 + (w1 - w0) * t
        soft_disc(x, y, w, col, 1.0)
    if hi:
        for i, (x, y) in enumerate(pts):
            t = i / max(1, n - 1)
            w = w0 + (w1 - w0) * t
            disc(x - w * 0.38, y - w * 0.18, max(1.0, w * 0.42), hi, 0.55)


def line(x0, y0, x1, y1, col, w=1.5):
    d = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(d / 1.2))
    for k in range(steps + 1):
        t = k / steps
        disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, w, col, 0.9)


# ---------------------------------------------------------------- font ----
# Small geometric stroke font on a 5x7 grid, drawn as round-cap strokes.
FONT = {
    'A': [[(0, 6), (2, 0), (4, 6)], [(1, 4), (3, 4)]],
    'C': [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    'E': [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    'G': [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5),
           (4, 3), (2, 3)]],
    'H': [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    'I': [[(2, 0), (2, 6)]],
    'L': [[(0, 0), (0, 6), (4, 6)]],
    'M': [[(0, 6), (0, 0), (2, 3), (4, 0), (4, 6)]],
    'N': [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    'O': [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1),
           (1, 0)]],
    'P': [[(0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]],
    'R': [[(0, 6), (0, 0), (4, 0), (4, 3), (0, 3)], [(2, 3), (4, 6)]],
    'S': [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4),
           (4, 5), (3, 6), (1, 6), (0, 5)]],
    'T': [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    'U': [[(0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)]],
    'V': [[(0, 0), (2, 6), (4, 0)]],
    'W': [[(0, 0), (1, 6), (2, 3), (3, 6), (4, 0)]],
    'Y': [[(0, 0), (2, 3), (4, 0)], [(2, 3), (2, 6)]],
    '0': [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1),
           (1, 0)]],
    '1': [[(1, 1), (2, 0), (2, 6)], [(0, 6), (4, 6)]],
    '2': [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (0, 6), (4, 6)]],
    '3': [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2)],
          [(2, 3), (4, 3), (4, 5), (3, 6), (1, 6), (0, 5)]],
    '4': [[(0, 0), (0, 3), (4, 3)], [(3, 0), (3, 6)]],
    '5': [[(4, 0), (0, 0), (0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6),
           (0, 5)]],
    '9': [[(0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)],
          [(0, 5), (1, 6), (2, 6)]],
    '$': [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4),
           (4, 5), (3, 6), (1, 6), (0, 5)], [(2, 0), (2, 6)]],
    '-': [[(0, 3), (4, 3)]],
    '·': [[(2, 3)]],
    '.': [[(2, 6)]],
    ' ': [],
}


def text_width(s, size):
    return len(s) * 6 * (size / 7.0) - (size / 7.0)


def draw_text(s, x, y, size, col, align="c"):
    sc = size / 7.0
    stroke = max(2.0, size / 6.0)
    total = text_width(s, size)
    if align == "c":
        x = x - total / 2.0
    elif align == "r":
        x = x - total
    for ch in s:
        glyph = FONT.get(ch)
        if glyph:
            for poly in glyph:
                pts = [(x + px * sc, y + py * sc) for px, py in poly]
                if len(pts) == 1:
                    soft_disc(pts[0][0], pts[0][1], stroke * 0.55, col)
                else:
                    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                        d = math.hypot(bx - ax, by - ay)
                        steps = max(1, int(d / (stroke * 0.45)))
                        for k in range(steps + 1):
                            t = k / steps
                            soft_disc(ax + (bx - ax) * t,
                                      ay + (by - ay) * t, stroke * 0.5, col)
        x += 6 * sc


# -------------------------------------------------------------- scene -----
INK = (61, 58, 53)
MUTED = (109, 103, 94)
COFFEE = (58, 33, 16)
COFFEE_HI = (126, 82, 44)


def render():
    # 1. studio backdrop: warm vertical gradient + soft radial key light
    top = (248, 245, 239)
    bot = (231, 225, 213)
    for y in range(H):
        t = y / (H - 1)
        col = tuple(int(round(top[c] + (bot[c] - top[c]) * t)) for c in range(3))
        span(y, 0, W, col)
    for i in range(18, 0, -1):
        f = i / 18.0
        ellipse(512, 470, 470 * f, 430 * f, (255, 255, 255), 0.012 * f)

    # 2. floor: warmer band below the horizon, feathered in
    floor_col = (222, 214, 198)
    for y in range(818, 878):
        a = min(1.0, (y - 818) / 40.0) * 0.55
        aspan(y, 0, W, floor_col, a)

    # 3. soft shadows (the mug floats, so its shadow is large and diffuse)
    soft_shadow(512, 868, 265, 32, alpha=0.24)
    soft_shadow(545, 848, 158, 21, alpha=0.28)

    # 4. saucer - the one accessory - with a pool of coffee on it
    ellipse(545, 836, 150, 25, (207, 200, 186))
    ellipse(545, 833, 146, 23, (250, 249, 246))
    ellipse(545, 831, 100, 16, (232, 229, 223))
    ellipse(545, 829, 50, 10, COFFEE)
    ellipse(543, 828, 32, 6, (125, 84, 44), 0.7)

    # 5. the impossible bit: coffee rising from the saucer, up the LEFT side
    #    of the mug, over the rim and down into the cup - never behind it
    stream = catmull([(545, 824), (488, 736), (418, 656),
                      (360, 552), (340, 440), (350, 336),
                      (400, 296), (470, 304), (505, 330)], steps=22)
    tube(stream, 16, 7, COFFEE, hi=COFFEE_HI)

    # suspended droplets that escaped the stream
    for (dx, dy, r) in [(430, 690, 6), (380, 590, 5), (345, 480, 6),
                        (380, 360, 5), (440, 300, 4), (330, 400, 4)]:
        disc(dx, dy, r, COFFEE)
        disc(dx - r * 0.35, dy - r * 0.35, max(1.0, r * 0.35),
             (255, 255, 255), 0.8)

    # 6. mug handle (behind the body so its ends tuck under the rim)
    handle = []
    for k in range(33):
        a = math.radians(-75 + 150 * k / 32)
        handle.append((636 + 92 * math.cos(a), 464 + 92 * math.sin(a)))
    tube(handle, 16, 16, (214, 207, 196), hi=(255, 255, 255))

    # 7. mug body: cream ceramic, lit from the left
    rrect(356, 316, 668, 612, 28, (255, 255, 255), (216, 209, 196))
    # bottom shade + left key-light band
    for y in range(566, 612):
        a = (y - 566) / 46.0 * 0.20
        aspan(y, 356, 668, (176, 168, 152), a)
    for y in range(330, 600):
        aspan(y, 382, 414, (255, 255, 255), 0.20)
        aspan(y, 390, 402, (255, 255, 255), 0.16)

    # 8. rim + coffee surface inside the cup
    ellipse(512, 316, 156, 32, (250, 250, 248))
    ellipse(512, 320, 142, 27, (96, 60, 32))
    ellipse(508, 318, 100, 17, (140, 92, 48), 0.6)
    # the stream crosses the rim and dives into the coffee (drawn on top)
    over = catmull([(392, 300), (430, 292), (470, 304), (505, 330)], steps=10)
    tube(over, 7, 6, COFFEE, hi=COFFEE_HI)
    ellipse(505, 330, 22, 7, (140, 92, 48), 0.85)  # ripple where it lands
    disc(498, 327, 2.5, (200, 150, 100), 0.9)

    # 9. product name printed on the mug
    draw_text("AEROCUP", 512, 470, 32, (74, 70, 64))
    draw_text("AG-1", 512, 512, 17, (120, 114, 106))

    # 10. catalogue furniture: brand, callouts, title, spec line
    draw_text("AEROCUP", 512, 56, 40, INK)
    line(392, 78, 632, 78, (180, 174, 162), 1.5)

    draw_text("POURS UPHILL", 300, 620, 24, INK, align="r")
    line(310, 632, 415, 652, (138, 131, 120), 1.5)
    disc(415, 652, 3, (138, 131, 120))

    draw_text("HOVERS AT 12 CM", 700, 620, 22, INK, align="l")
    line(690, 632, 625, 655, (138, 131, 120), 1.5)
    disc(625, 655, 3, (138, 131, 120))

    draw_text("THE ANTI-GRAVITY MUG", 512, 896, 30, INK)
    draw_text("350 ML · WEIGHS 0 G · $249", 512, 938, 20, MUTED)


# -------------------------------------------------------------- output ----
def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        raw += canvas[y * W * 3:(y + 1) * W * 3]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    render()
    n = write_png(OUT)
    print("wrote %s: %dx%d, %d bytes" % (OUT, W, H, n))
    assert n <= 1048576, "PNG exceeds 1 MiB"


if __name__ == "__main__":
    main()
