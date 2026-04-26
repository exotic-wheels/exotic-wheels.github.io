#!/usr/bin/env python3
"""
scripts/build_index.py

Fetches all GH release assets for this repo and generates a PEP 503
simple/ index. Wheels live on GH Releases. HTML lives on Cloudflare Pages.

Usage:
    python scripts/build_index.py

Requires: gh CLI authenticated, or set GITHUB_TOKEN env var.

The index pip actually queries is:
    https://exotic-wheels.pages.dev/simple/<pkgname>/index.html
Users just pass:
    pip install cryptography --extra-index-url https://exotic-wheels.pages.dev/
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen, Request

REPO         = "1minds3t/exotic-wheels"
PAGES_BASE   = "https://exotic-wheels.pages.dev"
REPO_ROOT    = Path(__file__).parent.parent
SIMPLE_DIR   = REPO_ROOT / "simple"

# ── GH API ───────────────────────────────────────────────────────────────────

def gh_releases() -> list[dict]:
    """Fetch all releases from GH API, handling pagination."""
    token = os.environ.get("GITHUB_TOKEN") or _gh_cli_token()
    releases = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{REPO}/releases?per_page=100&page={page}"
        req = Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        })
        with urlopen(req) as r:
            batch = json.loads(r.read())
        if not batch:
            break
        releases.extend(batch)
        page += 1
    return releases


def _gh_cli_token() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        print("ERROR: No GITHUB_TOKEN and gh CLI not authenticated.")
        print("Run: gh auth login")
        sys.exit(1)

# ── wheel helpers ─────────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    """PEP 503 normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def wheel_project(filename: str) -> str:
    return normalize(filename.split("-")[0])


# ── HTML ─────────────────────────────────────────────────────────────────────

def html(title: str, body: str) -> str:
    return (
        f'<!DOCTYPE html>\n<html>\n  <head><meta name="pypi:repository-version" '
        f'content="1.0"><title>{title}</title></head>\n'
        f'  <body>\n    <h1>{title}</h1>\n{body}\n  </body>\n</html>\n'
    )

# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching releases from {REPO}...")
    releases = gh_releases()
    print(f"  Found {len(releases)} releases")

    # Collect all wheel assets grouped by normalized project name
    # { "cryptography": [ {name, url}, ... ], ... }
    projects: dict[str, list[dict]] = {}

    for release in releases:
        for asset in release.get("assets", []):
            name = asset["name"]
            if not name.endswith(".whl"):
                continue
            proj = wheel_project(name)
            projects.setdefault(proj, []).append({
                "name": name,
                "url":  asset["browser_download_url"],
            })

    if not projects:
        print("No wheel assets found in any release.")
        return

    # Rebuild simple/
    import shutil
    if SIMPLE_DIR.exists():
        shutil.rmtree(SIMPLE_DIR)
    SIMPLE_DIR.mkdir()

    # Root index
    root_links = "\n".join(
        f'    <a href="{name}/">{name}</a>'
        for name in sorted(projects)
    )
    (SIMPLE_DIR / "index.html").write_text(
        html("Simple Index", root_links)
    )
    print(f"  simple/index.html  ({len(projects)} packages)")

    # Per-project index
    for proj_name, assets in sorted(projects.items()):
        proj_dir = SIMPLE_DIR / proj_name
        proj_dir.mkdir()

        links = "\n".join(
            f'    <a href="{a["url"]}">{a["name"]}</a>'
            for a in sorted(assets, key=lambda x: x["name"])
        )
        (proj_dir / "index.html").write_text(
            html(f"Links for {proj_name}", links)
        )
        print(f"  simple/{proj_name}/index.html  ({len(assets)} wheels)")

    print()
    print("Index generated. Test locally:")
    print("  python -m http.server 8080 --directory .")
    print("  pip install cryptography \\")
    print("    --extra-index-url http://localhost:8080/ \\")
    print("    --only-binary :all: --dry-run")
    print()
    print("Then commit and push:")
    print("  git add simple/")
    print('  git commit -m "chore: regenerate index"')
    print("  git push")


if __name__ == "__main__":
    main()