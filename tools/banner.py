#!/usr/bin/env python3
"""Renders the banners: art/banner.svg from art/src/banner.png, and the
rotation, art/banners/NN.svg from art/src/banners/NN.png.

The sources are Animagine XL 4.0 and Anima Turbo images, stored at the width
the effect works at, rendered with their generation seed. The settings below
are the banners'; change them here to iterate.

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

# How the echoes are laid out over a rotation banner.
VARIANTS = {
    "vignette": dict(echo_mode="near", ramp="vignette", ramp_start=0.45, power=1.6),
    # echoes ramping in toward the right edge
    "ramp": dict(echo_mode="near", ramp_start=0.35),
    # the same ramp on a mirrored copy, flipped back: echoes on the left
    "left": dict(echo_mode="near", ramp_start=0.35, mirror=True, unmirror=True),
}

# (name, seed, variant) for each source in art/src/banners/: the 1992 Sailor
# Moon look described in prose to Anima Turbo, no LoRA.
ROTATION = [
    ("01", 469447621, "ramp"),
    ("02", 250227419, "left"),
    ("03", 1055528820, "left"),
    ("04", 836750546, "ramp"),
    ("05", 305367374, "ramp"),
    ("06", 755395224, "ramp"),
    ("07", 922033397, "vignette"),
    ("08", 1014762417, "ramp"),
    ("09", 142252708, "ramp"),
    ("10", 881868366, "vignette"),
    ("11", 968396261, "ramp"),
    ("12", 1057678242, "ramp"),
    ("13", 77278188, "left"),
    ("14", 755365641, "ramp"),
    ("15", 610154809, "ramp"),
    ("16", 305650243, "ramp"),
]


def write(img, out, **settings):
    svg = glitch.render(img, **settings)
    with open(os.path.join(ROOT, out), "w") as f:
        f.write(svg)
    print(f"{out}: {len(svg) // 1024} KB", file=sys.stderr)


def main():
    write(Image.open(os.path.join(ROOT, "art/src/banner.png")), "art/banner.svg", **SETTINGS)
    os.makedirs(os.path.join(ROOT, "art/banners"), exist_ok=True)
    for name, seed, variant in ROTATION:
        img = Image.open(os.path.join(ROOT, f"art/src/banners/{name}.png"))
        write(img, f"art/banners/{name}.svg", seed=seed, lzss_seed=seed, **VARIANTS[variant])


if __name__ == "__main__":
    main()
