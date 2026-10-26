# Installation

## Requirements

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) (Python package and environment manager)
- A Rust toolchain, installed with [rustup](https://rustup.rs/). The Rust core is compiled during installation.
- Linux, macOS, or Windows. The Rust core links Intel MKL statically through `ndarray-linalg`, so the first build
  downloads MKL and takes several minutes.

## Install

```bash
git clone <repository-url> dspant
cd dspant
uv sync --extra emgproc
```

This creates `.venv/`, installs the Python dependencies pinned in `uv.lock`, and builds two Rust extensions with
maturin: `dspant._rs` (from `rust/`) and `dspant_emgproc._rs` (from `dspant_emgproc/rust/`).

Check the installation:

```bash
uv run python -c "import dspant, dspant_emgproc; print('ok')"
```

## Optional extras

| Extra | Adds |
|---|---|
| `emgproc` | The EMG extension (onset and offset detection). Needed by the figure scripts. |
| `dev` | `ipykernel` and `ruff` for interactive use and linting. |
| `cpu` / `cu128` | PyTorch (CPU or CUDA 12.8 build) for the few optional modules that use it. Choose one. |

Example: `uv sync --extra emgproc --extra dev`.

## Rebuilding after changes to the Rust code

```bash
uv sync --reinstall-package dspant --reinstall-package dspant-emgproc
```
