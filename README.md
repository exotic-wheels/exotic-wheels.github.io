<!-- banner / header -->
<img src="/banner.svg" alt="exotic-wheels platform coverage">

# exotic-wheels 

Pre-built wheels for platforms PyPI forgot.

```
pip install cryptography --extra-index-url https://exotic-wheels.github.io/
```

→ **[exotic-wheels.github.io](https://exotic-wheels.github.io/)** — landing page + full package list

---

**Why?** Packages like `cryptography` ship no wheels for `musllinux_1_2_armv7l`, `aarch64 musl`, and other exotic targets. Source builds require native toolchains, fail in CI, and break reproducible deploys. This index fills those gaps.

**How?** Wheels are built once in podman containers against the correct sysroot, uploaded to GitHub Releases, and served as a [PEP 503](https://peps.python.org/pep-0503/) compliant index. Drop-in for pip — no custom tooling required.

**Trust?** Every wheel links to its GH Release with SHA and upstream source version. No magic.

---

Part of the [omnipkg](https://github.com/1minds3t) ecosystem. Need a wheel? [Open an issue](https://github.com/exotic-wheels/exotic-wheels.github.io/issues/new).
