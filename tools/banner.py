#!/usr/bin/env python3
"""Renders art/banner.svg from art/src/banner.png.

The source is an Animagine XL 4.0 image (seed 888237246), stored at the
width the effect works at. The settings below are the banner's; change them
here to iterate.

    python3 tools/banner.py
"""
import os
import sys

from PIL import Image

import glitch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 888237246
SETTINGS = dict(
    seed=SEED,
    lzss_seed=SEED,
    echo_mode="near",  # echoes only near ink, none over empty paper
    ramp="vignette",  # echoes grow toward every edge, the middle stays clean
    ramp_start=0.45,
    power=1.6,
)


def main():
    img = Image.open(os.path.join(ROOT, "art/src/banner.png"))
    svg = glitch.render(img, **SETTINGS)
    with open(os.path.join(ROOT, "art/banner.svg"), "w") as f:
        f.write(svg)
    print(f"art/banner.svg: {len(svg) // 1024} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
