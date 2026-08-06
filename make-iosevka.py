#!/usr/bin/env python3
"""Fetch upstream Iosevka and cut down the four faces flow embeds.

Flow embeds Iosevka as its built-in default and last-resort fallback, so the
faces have to be small enough to live in every binary. Upstream ships them as
~50 MB TTC collections; this produces ~1.2 MB single-face TTFs.

Usage:
    ./make-iosevka.py [version]

Requires: curl, pyftsubset (Debian: fonttools, Arch: python-fonttools).
"""

import os
import shutil
import subprocess
import sys
import zipfile

DEFAULT_VERSION = "34.8.0"

# We want plain Iosevka only. Verify indexes with:
#   ./make-iosevka.py --list
#
# Medium (500) and ExtraBold (800) rather than Regular/Bold: those are the
# weights flow's fontweight/fontweight_bold_offset defaults resolve to, so the
# built-in face matches a system-installed Iosevka out of the box.
FACES = [
    ("Medium", 0, "Iosevka-Medium.ttf"),
    ("Medium", 3, "Iosevka-MediumItalic.ttf"),
    ("ExtraBold", 0, "Iosevka-ExtraBold.ttf"),
    ("ExtraBold", 3, "Iosevka-ExtraBoldItalic.ttf"),
]

# Do NOT pass --layout-features='*': that retains the ss/cv features and drags
# all ~39k alternate glyphs back in. pyftsubset's default feature set
# already keeps calt/liga/clig/rlig, which is where Iosevka's coding
# ligatures live.
SUBSET_ARGS = [
    "--unicodes=*",  # every encoded codepoint
    "--drop-tables+=GPOS",  # kerning/mark positioning, unusable without a shaper (~1.4 MB/face)
    "--no-glyph-names",  # drops post glyph names (~0.9 MB/face)
    "--notdef-outline",  # keep the .notdef box
]


def run(cmd, **kw):
    print("+", " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True, **kw)


def fetch(version, cache):
    zip_name = f"PkgTTC-SGr-Iosevka-{version}.zip"
    zip_path = os.path.join(cache, zip_name)
    if not os.path.exists(zip_path):
        url = f"https://github.com/be5invis/Iosevka/releases/download/v{version}/{zip_name}"
        run(["curl", "-fL", "--progress-bar", "-o", zip_path, url])

    ttc_dir = os.path.join(cache, f"PkgTTC-SGr-Iosevka-{version}")
    if not os.path.isdir(ttc_dir):
        os.makedirs(ttc_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(ttc_dir)

    license_path = os.path.join(cache, "LICENSE.md")
    if not os.path.exists(license_path):
        url = (
            f"https://raw.githubusercontent.com/be5invis/Iosevka/v{version}/LICENSE.md"
        )
        run(["curl", "-fL", "--progress-bar", "-o", license_path, url])

    return ttc_dir, license_path


def ttc_path(ttc_dir, weight):
    """The zip may or may not nest the .ttc files in a subdirectory."""
    name = f"SGr-Iosevka-{weight}.ttc"
    for root, _dirs, files in os.walk(ttc_dir):
        if name in files:
            return os.path.join(root, name)
    sys.exit(f"error: {name} not found under {ttc_dir}")


def list_faces(ttc_dir):
    """Print the faces in each TTC, so the FACES indices can be re-checked."""
    from fontTools.ttLib import TTCollection

    for weight in sorted({w for w, _, _ in FACES}):
        path = ttc_path(ttc_dir, weight)
        print(f"\n{os.path.basename(path)}:")
        for i, font in enumerate(TTCollection(path).fonts):
            name = font["name"].getDebugName(4) or "?"
            print(f"  [{i}] {name}")


def main():
    args = [a for a in sys.argv[1:]]
    do_list = "--list" in args
    if do_list:
        args.remove("--list")
    version = args[0] if args else DEFAULT_VERSION

    if not shutil.which("pyftsubset"):
        sys.exit("error: pyftsubset not found (Debian: apt install fonttools)")

    here = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(here, ".cache")
    out_dir = os.path.join(here, f"iosevka-{version}")
    os.makedirs(cache, exist_ok=True)

    ttc_dir, license_path = fetch(version, cache)

    if do_list:
        list_faces(ttc_dir)
        return

    os.makedirs(out_dir, exist_ok=True)
    # Drop stale faces so a re-cut with different weights leaves nothing behind.
    for stale in os.listdir(out_dir):
        if stale.endswith(".ttf"):
            os.remove(os.path.join(out_dir, stale))
    shutil.copyfile(license_path, os.path.join(out_dir, "LICENSE.md"))

    total = 0
    for weight, index, out_name in FACES:
        src = ttc_path(ttc_dir, weight)
        dst = os.path.join(out_dir, out_name)
        run(
            [
                "pyftsubset",
                src,
                f"--font-number={index}",
                *SUBSET_ARGS,
                f"--output-file={dst}",
            ]
        )
        size = os.path.getsize(dst)
        total += size
        print(f"  {out_name:24s} {size / 1024 / 1024:6.2f} MB")

    print(f"  {'total':24s} {total / 1024 / 1024:6.2f} MB")
    print(f"\nwrote {out_dir}")
    print("remember to list the directory in build.zig.zon .paths")


if __name__ == "__main__":
    main()
