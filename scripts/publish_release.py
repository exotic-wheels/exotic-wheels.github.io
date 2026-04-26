#!/usr/bin/env python3
"""
scripts/publish_release.py

Creates a GH release on exotic-wheels/exotic-wheels.github.io and uploads
all matching wheels from a local directory.

Usage:
    python scripts/publish_release.py cryptography 47.0.0 ~/omnipkg/ci-wheel-cache/retagged/
    python scripts/publish_release.py psutil 7.2.2 ~/build/wheels/

Requires: gh CLI authenticated with access to exotic-wheels org.
"""
import subprocess, sys
from pathlib import Path

REPO = "exotic-wheels/exotic-wheels.github.io"


def main():
    if len(sys.argv) < 4:
        print("Usage: publish_release.py <package> <version> <wheels-dir>")
        sys.exit(1)

    pkg     = sys.argv[1]
    version = sys.argv[2]
    wdir    = Path(sys.argv[3]).expanduser()
    tag     = f"{pkg}-{version}"

    # Find wheels for this package+version
    patterns = [
        f"{pkg.replace('-', '_')}*{version}*.whl",
        f"{pkg}*{version}*.whl",
    ]
    wheels = []
    seen = set()
    for pat in patterns:
        for w in sorted(wdir.glob(pat)):
            if w.name not in seen:
                seen.add(w.name)
                wheels.append(w)

    if not wheels:
        print(f"No wheels found for {pkg} {version} in {wdir}")
        sys.exit(1)

    print(f"Creating release {tag} on {REPO} with {len(wheels)} wheels:")
    for w in wheels:
        print(f"  {w.name}")

    cmd = [
        "gh", "release", "create", tag,
        "--repo", REPO,
        "--title", f"{pkg} {version} - exotic platform wheels",
        "--notes", (
            f"Pre-built wheels for **{pkg} {version}** on exotic platforms "
            f"(musllinux armv7l, etc.) with no PyPI wheels.\n\n"
            f"```\n"
            f"pip install {pkg} --extra-index-url https://exotic-wheels.github.io/\n"
            f"```"
        ),
    ] + [str(w) for w in wheels]

    subprocess.run(cmd, check=True)
    print(f"\nDone. Run build_index.py to regenerate the index.")


if __name__ == "__main__":
    main()