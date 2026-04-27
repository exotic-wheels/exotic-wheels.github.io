#!/usr/bin/env python3
"""
migrate_wheels.py — move wheel files into ~/.cache/exotic-wheels/<package>/

Usage:
    # migrate from ci-wheel-cache (one-time)
    python migrate_wheels.py --from ~/omnipkg/ci-wheel-cache

    # migrate from any dir
    python migrate_wheels.py --from ~/some/build/output

    # dry run first (always a good idea)
    python migrate_wheels.py --from ~/omnipkg/ci-wheel-cache --dry-run

    # list what's in the cache
    python migrate_wheels.py --list
"""
import re, shutil, sys
from argparse import ArgumentParser
from pathlib import Path

CACHE = Path.home() / ".cache" / "exotic-wheels"

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def pkg_from_wheel(filename):
    # e.g. cffi-2.0.0-cp310-cp310-linux_armv7l.whl -> cffi
    return normalize(filename.split("-")[0])

def migrate(src_dir: Path, dry_run: bool):
    src_dir = src_dir.expanduser().resolve()
    if not src_dir.exists():
        print(f"ERROR: {src_dir} does not exist"); sys.exit(1)

    wheels = sorted(src_dir.rglob("*.whl"))
    if not wheels:
        print(f"No .whl files found under {src_dir}"); return

    print(f"Found {len(wheels)} wheels in {src_dir}")
    if dry_run:
        print("DRY RUN — nothing will be moved\n")

    moved, skipped, errors = 0, 0, 0
    by_pkg: dict[str, list[Path]] = {}

    for w in wheels:
        pkg = pkg_from_wheel(w.name)
        by_pkg.setdefault(pkg, []).append(w)

    for pkg in sorted(by_pkg):
        dest_dir = CACHE / pkg
        print(f"\n  {pkg}/  ({len(by_pkg[pkg])} wheels)")
        for w in sorted(by_pkg[pkg]):
            dest = dest_dir / w.name
            if dest.exists():
                print(f"    skip (exists): {w.name}")
                skipped += 1
                continue
            print(f"    {'[DRY] ' if dry_run else ''}move: {w.name}")
            if not dry_run:
                dest_dir.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(str(w), dest)
                    moved += 1
                except Exception as e:
                    print(f"    ERROR: {e}")
                    errors += 1
            else:
                moved += 1

    print(f"\n{'[DRY] ' if dry_run else ''}Done: {moved} moved, {skipped} skipped, {errors} errors")
    if not dry_run and moved:
        print(f"Cache: {CACHE}")
        _print_cache()

def list_cache():
    if not CACHE.exists():
        print(f"Cache empty or not created yet: {CACHE}"); return
    total = 0
    for pkg_dir in sorted(CACHE.iterdir()):
        if not pkg_dir.is_dir(): continue
        wheels = sorted(pkg_dir.glob("*.whl"))
        if not wheels: continue
        print(f"\n  {pkg_dir.name}/  ({len(wheels)} wheels)")
        for w in wheels:
            size = w.stat().st_size
            print(f"    {w.name}  ({size // 1024}KB)")
        total += len(wheels)
    print(f"\nTotal: {total} wheels in {CACHE}")

def _print_cache():
    if not CACHE.exists(): return
    pkgs = [d for d in CACHE.iterdir() if d.is_dir()]
    total = sum(len(list(p.glob("*.whl"))) for p in pkgs)
    print(f"\nCache summary: {total} wheels across {len(pkgs)} packages")
    for p in sorted(pkgs):
        n = len(list(p.glob("*.whl")))
        print(f"  ~/.cache/exotic-wheels/{p.name}/  ({n} wheels)")

def main():
    ap = ArgumentParser(description="Exotic-wheels local cache manager")
    ap.add_argument("--from", dest="src", help="Source dir to migrate wheels from")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen, don't move")
    ap.add_argument("--list", action="store_true", help="List current cache contents")
    args = ap.parse_args()

    if args.list:
        list_cache(); return
    if args.src:
        migrate(Path(args.src), args.dry_run); return

    ap.print_help()

if __name__ == "__main__":
    main()