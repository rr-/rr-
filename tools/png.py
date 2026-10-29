#!/usr/bin/env python3
"""Renders every banner of art/banners/ into build/banners/NN-light.png and
NN-dark.png, for bad.pink to serve. The SVGs redraw their echoes as hundreds
of clipped copies of the whole path, which takes browsers seconds; a PNG
decodes instantly.

Each is 2304 px wide, twice the SVG's grid, so every dither dot is a whole
4x4 block; the browser downscales it. pngquant cuts the curves' 256 alpha
levels to 8 colors, which looks the same, and zopflipng packs the rest.

    python3 tools/png.py
"""
import glob
import os
import subprocess
import sys
import tempfile
from multiprocessing import Pool

from preview import forced

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "banners")
WIDTH = 2304


def render(job):
    path, theme = job
    name = os.path.splitext(os.path.basename(path))[0]
    out = os.path.join(OUT, f"{name}-{theme}.png")
    with open(path) as f:
        svg = forced(f.read(), theme == "dark")
    with tempfile.TemporaryDirectory() as tmp:
        src, raw, small = (os.path.join(tmp, n) for n in ("in.svg", "raw.png", "small.png"))
        with open(src, "w") as f:
            f.write(svg)
        subprocess.run(["rsvg-convert", "-w", str(WIDTH), src, "-o", raw], check=True)
        subprocess.run(["pngquant", "--force", "--speed", "1", "--output", small, "8", raw], check=True)
        subprocess.run(["zopflipng", "-y", "-m", small, out], check=True, capture_output=True)
    return out, os.path.getsize(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [(p, t) for p in sorted(glob.glob(os.path.join(ROOT, "art", "banners", "*.svg"))) for t in ("light", "dark")]
    with Pool() as pool:
        for out, size in pool.imap(render, jobs):
            print(f"{os.path.relpath(out, ROOT)}: {size // 1024} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
