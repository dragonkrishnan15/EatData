# EatData Packaging and Distribution Guide

## 1. Distribution Strategy

EatData is packaged as a standard, reproducible Python wheel (`.whl`) and source distribution (`.tar.gz`) utilizing `hatchling` and `uv build`.

### Artifact Specification
- **Package Name**: `eatdata`
- **Console Entrypoint**: `workbench = workbench.cli.main:main`
- **Embedded Assets**: Offline HTML5/CSS3 desktop UI embedded directly at `workbench/ui/app.html`. Zero external network requests (no CDNs, no remote fonts, no telemetry).
- **Supported Python Runtimes**: Python >= 3.11 (tested on CPython 3.11, 3.12, 3.13, 3.14, 3.15).
- **Supported Operating Systems**:
  - Windows 10/11 (x86_64, ARM64)
  - macOS >= 12.0 (Apple Silicon, Intel)
  - Linux (Ubuntu, Debian, Fedora, Arch, Alpine with glibc/musl)

---

## 2. Reproducible Build Procedure

To build the release distributions from source:

```bash
# 1. Ensure clean git state and passing tests
uv run pytest
uv run ruff check .

# 2. Build distribution archives
uv build
```

This generates:
- `dist/eatdata-<version>-py3-none-any.whl`
- `dist/eatdata-<version>.tar.gz`

---

## 3. Installation Methods

### A. Isolated Installation via `uvx` / `pipx` (Recommended)
```bash
pipx install dist/eatdata-0.1.0-py3-none-any.whl
# Or directly from wheel
workbench --help
```

### B. Standard `pip` Installation
```bash
pip install dist/eatdata-0.1.0-py3-none-any.whl
```

### C. Standalone Binary Compilation (PyInstaller Evaluation)
For air-gapped environments without Python pre-installed:
```bash
pyinstaller --name workbench --onefile \
  --add-data "src/workbench/ui/app.html;workbench/ui" \
  src/workbench/cli/main.py
```

---

## 4. Security & Privacy Release Checklist

- [x] Zero hardcoded API keys or external secrets.
- [x] Zero remote phone-home, analytics, or telemetry pings.
- [x] Desktop HTTP server strictly bound to loopback `127.0.0.1` (Rule 10).
- [x] SQLite persistence contains zero raw dataset rows or cell contents (Rules 2, 6, 14).
- [x] AI metadata payload allowlist verified with column aliasing support.
- [x] Formula injection protection enabled by default on CSV/Excel exports.
- [x] Source file overwrite protection enabled by default.
