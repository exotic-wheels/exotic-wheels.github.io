#!/usr/bin/env python3
"""
scripts/build_index.py — PEP 503 index generator for exotic-wheels.

Outputs package indexes to ROOT-LEVEL dirs (no /simple/ prefix) so that:
  https://exotic-wheels.github.io/          ← landing page + hidden pip root index
  https://exotic-wheels.github.io/uv-ffi/  ← pip package page

The landing page (index.html) gets a hidden PEP 503 block injected between
  <!-- PIP-INDEX-START --> and <!-- PIP-INDEX-END -->
markers so it's idempotent — safe to run multiple times.

pip finds the hidden <a href="uv-ffi/"> tags and follows them.
Humans see the landing page. Both work at the same URL.

For packages in MERGE_WITH_PYPI: merges PyPI wheels + our GH release wheels.
For packages in EXTRA_REPOS: links directly to a different GH repo's releases.
For all other packages: ONLY serves our GH release wheels.

Usage:
    python scripts/build_index.py
Requires: gh CLI authenticated, or GITHUB_TOKEN env var.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

REPO      = "exotic-wheels/exotic-wheels.github.io"
REPO_ROOT = Path(__file__).parent.parent

# Markers — must stay in sync with index.html
PIP_START = "<!-- PIP-INDEX-START -->"
PIP_END   = "<!-- PIP-INDEX-END -->"

# Only these packages get their PyPI wheels merged in.
MERGE_WITH_PYPI = {
    "omnipkg",
}

# Packages whose wheels live in a different GH repo's releases.
EXTRA_REPOS = {
    "cffi":         "1minds3t/exotic-wheels",
    "psutil":       "1minds3t/exotic-wheels",
    "cryptography": "1minds3t/exotic-wheels",
    "uv-ffi":       "1minds3t/uv-ffi",
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


def pkg_index_html(title, wheels):
    """PEP 503 per-package page — plain, pip-compatible."""
    links = "\n".join(
        f'    <a href="{u}">{f}</a>' for f, u in sorted(wheels.items())
    )
    return (
        f'<!DOCTYPE html>\n<html>\n  <head>\n    <meta charset="utf-8">\n'
        f'    <meta name="pypi:repository-version" content="1.0">\n'
        f'    <title>{title}</title>\n  </head>\n'
        f'  <body>\n    <h1>{title}</h1>\n{links}\n  </body>\n</html>\n'
    )


def inject_pip_block(index_html: Path, projects: dict):
    """
    Inject (or replace) the hidden PEP 503 root block into index.html.
    Block is wrapped in PIP-INDEX-START / PIP-INDEX-END markers.
    Safe to call multiple times — replaces existing block, never duplicates.
    """
    if not index_html.exists():
        print(f"  WARNING: {index_html} not found — skipping pip block injection")
        return

    content = index_html.read_text(encoding="utf-8")

    # Build the new block
    pkg_links = "\n".join(
        f'    <a href="{n}/">{n}</a>' for n in sorted(projects)
    )
    new_block = (
        f"{PIP_START}\n"
        f'<div style="display:none" aria-hidden="true">\n'
        f'  <!-- PEP 503 pip index — hidden from humans, readable by pip -->\n'
        f'{pkg_links}\n'
        f'</div>\n'
        f"{PIP_END}"
    )

    if PIP_START in content and PIP_END in content:
        # Replace existing block
        before = content[:content.index(PIP_START)]
        after  = content[content.index(PIP_END) + len(PIP_END):]
        updated = before + new_block + after
        print(f"  Replaced existing pip block in {index_html.name}")
    elif "</body>" in content:
        # Inject just before </body>
        updated = content.replace("</body>", f"\n{new_block}\n</body>")
        print(f"  Injected pip block into {index_html.name}")
    else:
        # Append to end
        updated = content.rstrip() + f"\n{new_block}\n"
        print(f"  Appended pip block to {index_html.name}")

    index_html.write_text(updated, encoding="utf-8")


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
            merged.update(wheels)
            print(f"  GH: {len(wheels)} | merged total: {len(merged)}")
        else:
            print(f"\nGH-only (exotic builds): {proj}  ({len(wheels)} wheels)")
            merged = dict(wheels)
        all_projects[proj] = merged

    # --- write per-package indexes to root-level dirs ---
    total = 0
    for proj, wheels in sorted(all_projects.items()):
        d = REPO_ROOT / proj
        # clean and recreate
        if d.exists() and d.is_dir():
            shutil.rmtree(d)
        d.mkdir()
        (d / "index.html").write_text(pkg_index_html(f"Links for {proj}", wheels))
        total += len(wheels)
        print(f"  {proj}/index.html  ({len(wheels)} wheels)")

    # --- inject hidden pip block into landing page ---
    inject_pip_block(REPO_ROOT / "index.html", all_projects)

    # --- remove old simple/ dir if it exists ---
    old_simple = REPO_ROOT / "simple"
    if old_simple.exists():
        shutil.rmtree(old_simple)
        print(f"\n  Removed old simple/ directory")

    print(f"\nDone. {total} wheels across {len(all_projects)} packages.")
    print('git add -A && git commit -m "chore: regenerate index" && git push')


if __name__ == "__main__":
    main()