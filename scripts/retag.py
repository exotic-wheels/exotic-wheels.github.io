#!/usr/bin/env python3
"""
scripts/retag.py — retag linux_armv7l wheels to musllinux_1_2_armv7l.

Usage:
    python scripts/retag.py <wheels-dir>
    python scripts/retag.py ~/omnipkg/ci-wheel-cache/retagged/

Finds all *-linux_armv7l.whl files in the given directory, rewrites the
filename and internal WHEEL metadata to musllinux_1_2_armv7l, and saves
the retagged wheel alongside the original.

Safe to run multiple times — skips wheels already retagged.
"""
import sys, os, zipfile
from pathlib import Path

FROM_TAG = "linux_armv7l"
TO_TAG   = "musllinux_1_2_armv7l"


def retag(src: Path) -> Path:
    dst = Path(str(src).replace(FROM_TAG, TO_TAG))
    if dst.exists():
        print(f"  skip (exists): {dst.name}")
        return dst

    tmp = dst.with_suffix(".tmp")
    with zipfile.ZipFile(src, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            new_name = item.filename.replace(FROM_TAG, TO_TAG)
            if item.filename.endswith("/WHEEL") or item.filename == "WHEEL":
                data = data.decode().replace(FROM_TAG, TO_TAG).encode()
            item.filename = new_name
            zout.writestr(item, data)
    tmp.replace(dst)
    print(f"  retagged → {dst.name}")
    return dst


def main():
    if len(sys.argv) < 2:
        print("Usage: retag.py <wheels-dir>")
        sys.exit(1)

    wdir = Path(sys.argv[1]).expanduser()
    wheels = sorted(wdir.glob(f"*-{FROM_TAG}.whl"))

    if not wheels:
        print(f"No *-{FROM_TAG}.whl files found in {wdir}")
        sys.exit(0)

    print(f"Found {len(wheels)} wheels to retag in {wdir}:")
    for w in wheels:
        retag(w)

    print(f"\nDone. Run publish_release.py to upload.")


if __name__ == "__main__":
    main()