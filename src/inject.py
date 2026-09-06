#!/usr/bin/env python3
"""
Unforced Error — stage 5: splice the payload into the page.

template.html carries __PAYLOAD_B64__ where the gzipped, base64'd corpus goes.
Keeping them apart means the data never has to pass through a conversation to
reach the page, and the template stays editable without re-emitting megabytes.

Runs wrap_for_pages.py and add_catalog_link.py last, because an Artifact
fragment served from GitHub Pages lands in quirks mode and renders UTF-8 as
Latin-1. Regenerating the page without these two silently undoes both.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
OUT = os.path.join(PROJ, "index.html")


def workspace_root(p):
    prev = None
    while p != prev:
        if os.path.isdir(os.path.join(p, "projects")):
            return p
        prev, p = p, os.path.dirname(p)
    return None


def main():
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    b64 = open(os.path.join(HERE, "data", "payload.b64"), encoding="utf-8").read().strip()
    assert "__PAYLOAD_B64__" in tpl, "template has no payload slot"
    html = tpl.replace("__PAYLOAD_B64__", b64)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("wrote %s — %.2f MB" % (OUT, len(html.encode("utf-8")) / 1e6))

    root = workspace_root(HERE)
    if not root:
        print("! no workspace root; skipped wrap + breadcrumb", file=sys.stderr)
        return
    tools = os.path.join(root, "catalog", "tools")
    for script in ("wrap_for_pages.py", "add_catalog_link.py"):
        path = os.path.join(tools, script)
        if os.path.exists(path):
            subprocess.check_call([sys.executable, path, OUT])
        else:
            print("! missing %s" % path, file=sys.stderr)


if __name__ == "__main__":
    main()
