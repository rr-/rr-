#!/usr/bin/env python3
"""Renders the profile's section headers, and holds the dither the banner
uses.

The dither is bad.pink's octant encoder up to the 1-bit stage (Bayer 4x4,
contrast, gamma, lineart edges). The headers are a 5x7 pixel font in a box,
in pink that switches with prefers-color-scheme.

    python3 tools/gen.py
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK_LIGHT = "#e0336f"
INK_DARK = "#f69"

BAYER4 = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

# 5x7 glyphs, rows top to bottom, "#" is ink.
FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ",": [".....", ".....", ".....", ".....", ".##..", "..#..", ".#..."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    "-": [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    "%": ["##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
}
GLYPH_W, GLYPH_H, ADVANCE = 5, 7, 6


class Bitmap:
    def __init__(self, w, h, bits=None):
        self.w, self.h = w, h
        self.bits = bits if bits is not None else [0] * (w * h)

    def get(self, x, y):
        return self.bits[y * self.w + x]

    def set(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.bits[y * self.w + x] = v

    def fill(self, x, y, w, h, v):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, v)

    def text(self, x, y, s, v=1, scale=1):
        for i, ch in enumerate(s.upper()):
            glyph = FONT[ch]
            for gy, row in enumerate(glyph):
                for gx, c in enumerate(row):
                    if c == "#":
                        self.fill(x + (i * ADVANCE + gx) * scale, y + gy * scale, scale, scale, v)


def text_width(s, scale=1):
    return (len(s) * ADVANCE - 1) * scale


def dither(img, cols, invert, contrast=1.35, gamma=0.72, lineart=0.8, brightness="luma"):
    """bad.pink's octant encoder up to the 1-bit stage (apps/main/octant).

    brightness="luma" is bad.pink's Rec.601 luma, which makes saturated reds
    dark (a red sun turns into a dark disc); "value" takes max(R, G, B)
    instead, so a bright color stays bright whatever its hue."""
    w = cols * 2
    h = max(1, round(cols * (img.height / img.width) / 2)) * 4
    rgb = list(img.convert("RGB").resize((w, h), Image.BILINEAR).getdata())
    if brightness == "value":
        g = [float(max(px)) for px in rgb]
    else:
        g = [0.299 * r + 0.587 * gg + 0.114 * b for (r, gg, b) in rgb]
    n = w * h
    mn, mx = min(g), max(g)
    rng = max(1.0, mx - mn)
    g = [(v - mn) / rng * 255 for v in g]
    g = [min(255.0, max(0.0, (v - 128) * contrast + 128)) for v in g]
    if lineart > 0:
        k = lineart * 0.8
        e = [0.0] * n
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                i = y * w + x
                gx = g[i + 1] - g[i - 1]
                gy = g[i + w] - g[i - w]
                e[i] = min(255.0, (gx * gx + gy * gy) ** 0.5)
        g = [max(0.0, g[i] - e[i] * k) for i in range(n)]
    g = [255 * (v / 255) ** gamma for v in g]
    if invert:
        g = [255 - v for v in g]
    bits = [0] * n
    for y in range(h):
        for x in range(w):
            t = (BAYER4[y & 3][x & 3] + 0.5) / 16 * 255
            bits[y * w + x] = 1 if g[y * w + x] > t else 0
    return Bitmap(w, h, bits)


def to_path(bm):
    """The bitmap's ink as one path of horizontal runs."""
    out = []
    cx = cy = 0  # where the pen is: each run closes back to its start
    for y in range(bm.h):
        x = 0
        while x < bm.w:
            if bm.get(x, y):
                start = x
                while x < bm.w and bm.get(x, y):
                    x += 1
                out.append(f"m{start - cx} {y - cy}h{x - start}v1h{start - x}z")
                cx, cy = start, y
            else:
                x += 1
    path = "".join(out)
    return "M" + path[1:] if path else path


def svg(light, dark, title, scale):
    """One SVG holding both variants; CSS shows the one for the theme."""
    w, h = light.w, light.h
    if dark is None:
        body = f'<path class="ink" d="{to_path(light)}"/>'
        style = (
            f".ink{{fill:{INK_LIGHT}}}"
            f"@media (prefers-color-scheme:dark){{.ink{{fill:{INK_DARK}}}}}"
        )
    else:
        body = (
            f'<path class="l" d="{to_path(light)}"/>'
            f'<path class="d" d="{to_path(dark)}"/>'
        )
        style = (
            f".l{{fill:{INK_LIGHT}}}.d{{fill:{INK_DARK};display:none}}"
            "@media (prefers-color-scheme:dark){.l{display:none}.d{display:inline}}"
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w * scale}" height="{h * scale}" shape-rendering="crispEdges" '
        f'role="img" aria-label="{title}"><title>{title}</title>'
        f"<style>{style}</style>{body}</svg>\n"
    )


def header(text):
    """A section heading: the text in a box with a drop shadow."""
    pad = 3
    w = text_width(text) + pad * 2 + 2 + 2
    h = GLYPH_H + pad * 2 + 2 + 2
    bm = Bitmap(w, h)
    bm.fill(2, 2, w - 2, h - 2, 1)
    bm.fill(0, 0, w - 2, h - 2, 0)
    bm.fill(0, 0, w - 2, 1, 1)
    bm.fill(0, h - 3, w - 2, 1, 1)
    bm.fill(0, 0, 1, h - 2, 1)
    bm.fill(w - 3, 0, 1, h - 2, 1)
    bm.text(1 + pad, 1 + pad, text)
    return svg(bm, None, text.lstrip("> ").capitalize(), 3)


HEADERS = {
    "now": "> NOW",
    "stuff": "> BIG STUFF",
    "small": "> SMALLER STUFF",
    "facts": "> ME",
}


def main():
    os.makedirs(os.path.join(ROOT, "art"), exist_ok=True)
    files = {}
    for name, text in HEADERS.items():
        files[f"art/{name}.svg"] = header(text)
    for path, content in files.items():
        with open(os.path.join(ROOT, path), "w") as f:
            f.write(content)
        print(f"{path}: {len(content) // 1024} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
