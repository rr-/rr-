#!/usr/bin/env python3
"""Builds build/preview.html: the README rendered twice, side by side, in
GitHub's light and dark colors. The art follows prefers-color-scheme, which a
page can't switch per column, so each column gets copies of the SVGs with the
theme forced.

With --watch it serves build/ on localhost, rebuilds whenever the README or
the art changes, and the page reloads itself.

    python3 tools/preview.py [--watch] [--port PORT]
"""
import argparse
import functools
import glob
import http.server
import os
import re
import threading
import time

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "build")
PROFILE = ROOT

DARK_ONLY = re.compile(r"@media \(prefers-color-scheme:dark\)\{(.*?)\}\}")


def forced(svg, dark):
    """The SVG with its theme fixed: the dark-mode rules applied, or dropped."""
    m = DARK_ONLY.search(svg)
    if not m:
        return svg
    rules = m.group(1) + "}"
    return svg[:m.start()] + (rules if dark else "") + svg[m.end():]


# Polls version.txt, which build() rewrites, and reloads when it changes.
RELOAD = """<script>
let seen;
setInterval(async () => {
  try {
    const v = await (await fetch("version.txt", {cache: "no-store"})).text();
    if (seen && v !== seen) location.reload();
    seen = v;
  } catch {}
}, 500);
</script>
"""


def build(live=False):
    os.makedirs(HERE, exist_ok=True)
    for theme in ("light", "dark"):
        os.makedirs(os.path.join(HERE, "preview", theme, "art"), exist_ok=True)
        for path in glob.glob(os.path.join(PROFILE, "art", "*.svg")):
            with open(path) as f:
                svg = f.read()
            out = os.path.join(HERE, "preview", theme, "art", os.path.basename(path))
            with open(out, "w") as f:
                f.write(forced(svg, theme == "dark"))
    with open(os.path.join(PROFILE, "README.md")) as f:
        body = markdown.markdown(f.read(), extensions=["md_in_html", "fenced_code"])
    cols = "".join(
        f'<div class="col {t}"><div class="name">{t} theme</div><article>'
        + body.replace('src="art/', f'src="preview/{t}/art/')
        + "</article></div>"
        for t in ("light", "dark")
    )
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>Profile preview</title>
<style>
body {{ margin: 0; font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI",
  "Noto Sans", Helvetica, Arial, sans-serif; display: flex; flex-wrap: wrap; }}
.col {{ flex: 1 1 600px; padding: 24px 32px; box-sizing: border-box; }}
.light {{ background: #fff; color: #1f2328; }}
.light a {{ color: #0969da; }}
.dark {{ background: #0d1117; color: #f0f6fc; }}
.dark a {{ color: #4493f8; }}
a {{ text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
article {{ max-width: 830px; margin: 0 auto; border: 1px solid #8884;
  border-radius: 6px; padding: 24px; }}
article img {{ max-width: 100%; vertical-align: middle; }}
ul {{ padding-left: 2em; }}
li + li {{ margin-top: .25em; }}
pre {{ background: #8881; padding: 16px; border-radius: 6px; overflow: auto; font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }}
.name {{ font: 12px monospace; opacity: .6; margin: 0 auto 8px; max-width: 830px; }}
</style>
{cols}
{RELOAD if live else ""}"""
    with open(os.path.join(HERE, "preview.html"), "w") as f:
        f.write(page)
    with open(os.path.join(HERE, "version.txt"), "w") as f:
        f.write(str(time.time()))


def sources():
    paths = [os.path.join(PROFILE, "README.md")] + glob.glob(os.path.join(PROFILE, "art", "*.svg"))
    return {p: os.path.getmtime(p) for p in paths if os.path.exists(p)}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def watch(port):
    build(live=True)
    handler = functools.partial(QuietHandler, directory=HERE)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"http://127.0.0.1:{port}/preview.html", flush=True)
    seen = sources()
    while True:
        time.sleep(0.3)
        now = sources()
        if now != seen:
            seen = now
            try:
                build(live=True)
                print(time.strftime("%H:%M:%S"), "rebuilt", flush=True)
            except Exception as e:
                print(time.strftime("%H:%M:%S"), "build failed:", e, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    if args.watch:
        watch(args.port)
    else:
        build()
        print(os.path.join(HERE, "preview.html"))


if __name__ == "__main__":
    main()
