#!/usr/bin/env python3
"""The banner effect: bad.pink's dither, Bézier echoes of the picture's
outlines, and Touhou 6's LZSS compression glitched at the bottom, as one SVG
that follows the page's light or dark theme.

The outlines come from potrace. Each echo is the same outlines through an
offset, shown in its own cell of the picture, the offset growing toward the
edges (a vignette) or the right. The bottom is torn in bands, each its own
LZSS stream (as th06 stores its archive entries) with damaged
back-references. Light: pink ink on the page; dark: that flipped, light pink
wherever the light one is empty, with its own tear.
"""
import base64
import io
import math
import random
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

import gen
import lzss

INK = gen.INK_LIGHT
INK_DARK = gen.INK_DARK
TOKEN = re.compile(r"[a-zA-Z]|-?\d+(?:\.\d+)?")


def brightness(img, contrast=1.35, gamma=0.72, lineart=0.8):
    """gen.dither's tone pipeline up to the 1-bit step, as an "L" image."""
    w, h = img.size
    g = [float(max(px)) for px in img.convert("RGB").getdata()]
    mn, mx = min(g), max(g)
    rng = max(1.0, mx - mn)
    g = [min(255.0, max(0.0, ((v - mn) / rng * 255 - 128) * contrast + 128)) for v in g]
    if lineart > 0:
        k = lineart * 0.8
        e = [0.0] * (w * h)
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                i = y * w + x
                gx, gy = g[i + 1] - g[i - 1], g[i + w] - g[i - w]
                e[i] = min(255.0, (gx * gx + gy * gy) ** 0.5)
        g = [max(0.0, g[i] - e[i] * k) for i in range(w * h)]
    out = Image.new("L", (w, h))
    out.putdata([round(255 * (v / 255) ** gamma) for v in g])
    return out


def trace(mask, turdsize=3, opttolerance=0.4):
    """potrace a mask (ink where black): subpaths as (start, [(c1, c2, end)]),
    absolute, in image pixels, y down."""
    with tempfile.TemporaryDirectory() as tmp:
        pbm = Path(tmp) / "m.pbm"
        mask.save(pbm)
        svg = subprocess.run(
            ["potrace", "-b", "svg", "--flat", "-t", str(turdsize), "-a", "1.0",
             "-O", str(opttolerance), "-u", "10", "-o", "-", str(pbm)],
            check=True, capture_output=True, text=True).stdout
    h = mask.height
    subpaths = []
    for d in re.findall(r' d="([^"]*)"', svg):
        tok = TOKEN.findall(d)
        i, cmd = 0, None
        x = y = sx = sy = 0.0
        cur = None
        while i < len(tok):
            if tok[i].isalpha():
                cmd = tok[i]
                i += 1
                if cmd in "zZ":
                    x, y = sx, sy  # closepath returns to the subpath's start
                    continue
            nums = []
            want = {"m": 2, "l": 2, "c": 6}[cmd.lower()]
            for _ in range(want):
                nums.append(float(tok[i]))
                i += 1
            rel = cmd.islower()
            if cmd in "mM":
                x, y = (x + nums[0], y + nums[1]) if rel else (nums[0], nums[1])
                sx, sy = x, y
                cur = ((x, y), [])
                subpaths.append(cur)
                cmd = "l" if rel else "L"  # extra pairs after m are lines
            elif cmd in "lL":
                nx, ny = (x + nums[0], y + nums[1]) if rel else (nums[0], nums[1])
                cur[1].append(((x + (nx - x) / 3, y + (ny - y) / 3),
                               (x + 2 * (nx - x) / 3, y + 2 * (ny - y) / 3), (nx, ny)))
                x, y = nx, ny
            else:
                pts = [(x + nums[j], y + nums[j + 1]) if rel else (nums[j], nums[j + 1]) for j in (0, 2, 4)]
                cur[1].append(tuple(pts))
                x, y = pts[2]

    def fix(p):  # tenths of a pixel, y up from the bottom
        return (p[0] / 10, h - p[1] / 10)

    return [(fix(s), [tuple(fix(p) for p in seg) for seg in segs]) for s, segs in subpaths]


def compact_d(subpaths, scale=2):
    """Path data as small as it gets: coordinates times `scale` as integers,
    relative cubics after an absolute start, one command letter per subpath,
    and no space before a minus sign."""
    out = []

    def nums(vals):
        s = ""
        for v in vals:
            t = str(v)
            s += t if (not s or t.startswith("-")) else " " + t
        return s

    for start, segs in subpaths:
        x, y = round(start[0] * scale), round(start[1] * scale)
        parts = ["M" + nums((x, y)) + "c"]
        body = []
        for c1, c2, end in segs:
            p = [round(v * scale) for v in (*c1, *c2, *end)]
            body += [p[0] - x, p[1] - y, p[2] - x, p[3] - y, p[4] - x, p[5] - y]
            x, y = p[4], p[5]
        parts.append(nums(body))
        out.append("".join(parts) + "z")
    return "".join(out)


def glitch_bands(bits, y0, hits, seed, rows=6, shears=0, every=False):
    """LZSS offset damage from row y0 down, in bands of `rows` rows that are
    each their own LZSS stream (like th06's archive entries), so a bad
    back-reference only smears its own band instead of everything after it.
    Further down, more bands get hit and harder: `hits` per band at the
    bottom."""
    rng = random.Random(seed)
    out = bits.copy()
    for y in range(y0, bits.height, rows):
        t = (y - y0) / max(1, bits.height - y0)
        if not every and rng.random() > 0.25 + 0.7 * t:
            continue
        band = bits.crop((0, y, bits.width, min(bits.height, y + rows)))
        n = max(1, round(hits * (0.2 + 0.8 * t)))
        hit = lzss.glitch(band, "offset", n, seed=rng.randrange(1 << 30), gray=True)
        # a bad copy length shifts the rest of the band sideways: a tear
        if shears and (every or rng.random() < 0.3 + 0.6 * t):
            hit = lzss.glitch(hit, "length", shears, seed=rng.randrange(1 << 30), gray=True)
        out.paste(hit, (0, y))
    return out.point(lambda v: 1 if v else 0)


def auto_threshold(tone, ink=0.35):
    """The threshold that makes `ink` of the picture ink (the darkest part)."""
    hist = tone.histogram()
    total, run = sum(hist), 0
    for v, n in enumerate(hist):
        run += n
        if run >= ink * total:
            return v + 1
    return 128


def render(img, width=576, seed=0, strength=2.0, echoes=10, strips=16, power=2.2,
                     ramp_start=0.0, stroke=1.2, keep=(), cut_frac=0.7, ink=0.25,
                     lzss_count=10, lzss_seed=1, lzss_rows=12, lzss_shears=1, echo_mode="draw", near=6,
                     mirror=False, ramp="right", unmirror=False):
    """The dither + Bézier echo + LZSS banner for both themes, on transparent.

    echo_mode: "draw" lays the echoes on top in ink; "near" does the same but
    only within `near` pixels of the ink, so no echo floats over empty paper;
    "xor" flips whatever is under each echo line, ink to paper and back.

    ramp: "right" grows the echoes from `ramp_start` of the width to the right
    edge; "vignette" grows them from `ramp_start` of the way out from the
    middle to every edge, in a grid of cells, so the middle stays clean.
    mirror flips the picture first; unmirror flips the finished result back,
    so the picture faces the original way and the echoes the other.

    No edge detection anywhere (lineart 0). Light theme: the dither of the
    dark tones with the curves on top, in pink. Dark theme: exactly that,
    flipped: light pink wherever the light theme is empty, so the dither and
    the curves become holes; its LZSS tear is its own, so it frays to
    transparent too. The echoes skip the `keep` shapes; the clean outlines
    stop at the LZSS cut."""
    if mirror:
        img = ImageOps.mirror(img)
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    w, h = img.size
    S = 2
    W, H, C = w * S, h * S, round(h * cut_frac) * S
    tone = brightness(img, lineart=0)
    mask = tone.point(lambda v, t=auto_threshold(tone, ink): 0 if v < t else 255).convert("1")
    d = compact_d(trace(mask, 5, opttolerance=1.0), S)

    bm = gen.dither(img, w // 2, invert=True, lineart=0, brightness="value")
    bits = Image.frombytes("L", (bm.w, bm.h), bytes(bm.bits))
    y0 = round(bm.h * cut_frac)
    # each theme tears its own ink: the light theme the dither, the dark one
    # its complement, so in both the damage frays into the page, not into ink
    ink_img = glitch_bands(bits, y0, lzss_count, lzss_seed, lzss_rows, lzss_shears)
    ink_img = ink_img.point(lambda v: 255 if v else 0).convert("1")
    paper_img = glitch_bands(bits.point(lambda v: 0 if v else 1), y0, lzss_count, lzss_seed, lzss_rows, lzss_shears)
    paper_img = paper_img.point(lambda v: 255 if v else 0).convert("1")
    near_img = ink_img.convert("L").filter(ImageFilter.MaxFilter(2 * near + 1)).convert("1")

    def image(id_, picture):
        buf = io.BytesIO()
        picture.save(buf, "PNG", optimize=True)
        return (f'<image id="{id_}" width="{W}" height="{H}" preserveAspectRatio="none" '
                f'style="image-rendering:pixelated" href="data:image/png;base64,'
                f'{base64.b64encode(buf.getvalue()).decode()}"/>')

    rng = random.Random(seed)
    dirs = []
    for k in range(1, echoes + 1):
        side = 1 if k % 2 else -1
        n = (k + 1) // 2
        dirs.append((side * n * 0.035 * W * rng.uniform(0.8, 1.2), n * 0.025 * H * rng.uniform(-1, 1)))
    # cells of the picture above the cut, each showing the echoes through
    # its own offset: a column per strip, or a grid for the vignette
    sw = W / strips
    rows = 1 if ramp == "right" else max(1, round(strips * C / W))
    sh = C / rows
    clips, groups = [], []
    for i in range(strips):
        for j in range(rows):
            u, v = (i + 0.5) / strips, (j + 0.5) / rows
            if ramp == "right":
                pos = (u - ramp_start) / (1 - ramp_start)
            else:
                r = min(1.0, math.hypot((u - 0.5) * 2, (v * C / H - 0.5) * 2))
                pos = (r - ramp_start) / (1 - ramp_start)
            t = max(0.0, pos) ** power * strength
            if t < 0.01:
                continue
            cid = f"s{i}_{j}"
            clips.append(f'<clipPath id="{cid}"><rect x="{round(i * sw)}" y="{round(j * sh)}" '
                         f'width="{round(sw) + 1}" height="{round(sh) + 1}"/></clipPath>')
            groups.append(f'<g clip-path="url(#{cid})">'
                          + "".join(f'<use href="#c" x="{round(dx * t)}" y="{round(dy * t)}"/>' for dx, dy in dirs) + "</g>")
    keepmask = ""
    if keep:
        keepmask = (f'<mask id="k" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
                    f'<rect width="{W}" height="{H}" fill="#fff"/><g transform="scale({S})">{"".join(keep)}</g></mask>')
    box = f'maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}"'
    lines = (f'<g id="ln" fill="none" stroke-width="{stroke * S}" stroke-linejoin="round">'
             f'<g{" mask=" + chr(34) + "url(#k)" + chr(34) if keep else ""}>{"".join(groups)}</g>'
             f'<use href="#c" clip-path="url(#top)"/></g>')
    extra = ""
    if echo_mode == "near":
        # the echoes only where there is ink close by
        extra = image("near", near_img)
        lines = (f'<mask id="nm" {box}><use href="#near"/></mask>'
                 f'<g id="ln" fill="none" stroke-width="{stroke * S}" stroke-linejoin="round">'
                 f'<g mask="url(#nm)"><g{" mask=" + chr(34) + "url(#k)" + chr(34) if keep else ""}>{"".join(groups)}</g></g>'
                 f'<use href="#c" clip-path="url(#top)"/></g>')
    if echo_mode == "xor":
        # a line turns ink into paper and paper into ink: the line's area
        # shows the inverted picture
        masks = (f'<mask id="lnm" {box}><rect width="{W}" height="{H}"/><use href="#ln" stroke="#fff"/></mask>'
                 f'<mask id="ml" {box}><use href="#ink"/><use href="#paper" mask="url(#lnm)"/></mask>'
                 f'<mask id="md" {box}><use href="#paper"/><use href="#ink" mask="url(#lnm)"/></mask>')
    else:
        masks = (f'<mask id="ml" {box}><use href="#ink"/><use href="#ln" stroke="#fff"/></mask>'
                 f'<mask id="md" {box}><use href="#paper"/><use href="#ln" stroke="#000"/></mask>')
    style = ".d{display:none}@media (prefers-color-scheme:dark){.l{display:none}.d{display:inline}}"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{w}" height="{h}">'
            f'<style>{style}</style><defs><path id="c" d="{d}"/>{"".join(clips)}'
            f'<clipPath id="top"><rect width="{W}" height="{C}"/></clipPath>{keepmask}{lines}'
            f'{image("ink", ink_img)}{image("paper", paper_img)}{extra}{masks}</defs>'
            f'<g{f" transform={chr(34)}matrix(-1 0 0 1 {W} 0){chr(34)}" if unmirror else ""}>'
            f'<rect class="l" width="{W}" height="{H}" fill="{INK}" mask="url(#ml)"/>'
            f'<rect class="d" width="{W}" height="{H}" fill="{INK_DARK}" mask="url(#md)"/></g></svg>\n')

