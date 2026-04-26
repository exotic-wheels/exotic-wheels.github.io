#!/usr/bin/env python3
"""
scripts/build_index.py — PEP 503 index generator for exotic-wheels.

For packages in MERGE_WITH_PYPI: merges PyPI wheels + our GH release wheels
  (our builds take priority, so exotic platforms override PyPI mainstream).
For packages in EXTRA_REPOS: scrapes wheels from a different GH repo's releases
  and merges them in (no duplication — just links to the source repo URLs).
For all other packages: ONLY serves our GH release wheels — no PyPI fallback.

Usage:
    python scripts/build_index.py
Requires: gh CLI authenticated, or GITHUB_TOKEN env var.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

REPO       = "exotic-wheels/exotic-wheels.github.io"
REPO_ROOT  = Path(__file__).parent.parent
SIMPLE_DIR = REPO_ROOT / "simple"

# Only these packages get their PyPI wheels merged in.
# Everything else is served ONLY from our GH releases.
MERGE_WITH_PYPI = {
    "omnipkg",
}

# Packages whose wheels live in a different GH repo's releases.
# We scrape them and link directly — no file copying, no duplication.
EXTRA_REPOS = {
    "uv-ffi": "1minds3t/uv-ffi",
}


def gh_token():
    if t := os.environ.get("GITHUB_TOKEN"):
        return t
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except Exception:
        print("ERROR: No GITHUB_TOKEN and gh CLI not authenticated."); sys.exit(1)


def gh_get(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}",
                                "Accept": "application/vnd.github+json"})
    with urlopen(req) as r:
        return json.loads(r.read())


def gh_releases(token, repo=REPO):
    releases, page = [], 1
    while True:
        batch = gh_get(
            f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}",
            token
        )
        if not batch: break
        releases.extend(batch); page += 1
    return releases


def gh_assets(release_id, token, repo=REPO):
    assets, page = [], 1
    while True:
        batch = gh_get(
            f"https://api.github.com/repos/{repo}/releases/{release_id}/assets?per_page=100&page={page}",
            token
        )
        if not batch: break
        assets.extend(batch); page += 1
    return assets


def pypi_wheels(pkg):
    try:
        with urlopen(Request(f"https://pypi.org/pypi/{pkg}/json",
                             headers={"Accept": "application/json"})) as r:
            data = json.loads(r.read())
        results = [(v, f["filename"], f["url"])
                   for v, files in data["releases"].items()
                   for f in files if f["filename"].endswith(".whl")]
        print(f"  PyPI: {len(results)} wheels merged for {pkg}")
        return results
    except URLError as e:
        print(f"  PyPI fetch failed for {pkg}: {e}"); return []


def normalize(name): return re.sub(r"[-_.]+", "-", name).lower()
def wheel_project(fn): return normalize(fn.split("-")[0])
def html(title, body):
    return (f'<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset="utf-8">\n'
            f'    <meta name="pypi:repository-version" content="1.0">\n'
            f'    <title>{title}</title>\n  </head>\n'
            f'  <body>\n    <h1>{title}</h1>\n{body}\n  </body>\n</html>\n')


def main():
    token = gh_token()

    # --- scrape primary repo ---
    print(f"Fetching GH releases from {REPO}...")
    releases = gh_releases(token)
    print(f"  Found {len(releases)} releases")

    gh_wheels = {}
    for rel in releases:
        for asset in gh_assets(rel["id"], token):
            if asset["name"].endswith(".whl"):
                proj = wheel_project(asset["name"])
                gh_wheels.setdefault(proj, {})[asset["name"]] = asset["browser_download_url"]

    # --- scrape extra repos ---
    for pkg, extra_repo in EXTRA_REPOS.items():
        print(f"\nFetching releases from extra repo: {extra_repo} (for {pkg})")
        extra_releases = gh_releases(token, repo=extra_repo)
        print(f"  Found {len(extra_releases)} releases")
        count = 0
        for rel in extra_releases:
            for asset in gh_assets(rel["id"], token, repo=extra_repo):
                if asset["name"].endswith(".whl"):
                    proj = wheel_project(asset["name"])
                    gh_wheels.setdefault(proj, {})[asset["name"]] = asset["browser_download_url"]
                    count += 1
        print(f"  Indexed {count} wheels from {extra_repo}")

    if not gh_wheels:
        print("No wheel assets found in any GH release."); return

    all_projects = {}
    for proj, wheels in gh_wheels.items():
        if proj in MERGE_WITH_PYPI:
            print(f"\nMerging PyPI + GH for: {proj}")
            merged = {}
            for _, fn, url in pypi_wheels(proj):
                merged[fn] = url
            merged.update(wheels)  # our builds override PyPI
            print(f"  GH: {len(wheels)} | merged total: {len(merged)}")
        else:
            print(f"\nGH-only (exotic builds): {proj}  ({len(wheels)} wheels)")
            merged = dict(wheels)
        all_projects[proj] = merged

    if SIMPLE_DIR.exists(): shutil.rmtree(SIMPLE_DIR)
    SIMPLE_DIR.mkdir()

    root = "\n".join(f'    <a href="{n}/">{n}</a>' for n in sorted(all_projects))
    (SIMPLE_DIR / "index.html").write_text(html("Simple Index", root))

    total = 0
    for proj, wheels in sorted(all_projects.items()):
        d = SIMPLE_DIR / proj; d.mkdir()
        links = "\n".join(f'    <a href="{u}">{f}</a>' for f, u in sorted(wheels.items()))
        (d / "index.html").write_text(html(f"Links for {proj}", links))
        total += len(wheels)
        print(f"  simple/{proj}/index.html  ({len(wheels)} wheels)")

    print(f"\nDone. {total} wheels across {len(all_projects)} packages.")
    print('git add simple/ && git commit -m "chore: regenerate index" && git push')

if __name__ == "__main__":
    main()