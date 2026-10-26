# dspant

> [!WARNING]
> **ARCHIVED REPOSITORY — PROVIDED "AS IS"**
>
> This repository is a static, frozen archival snapshot accompanying the published manuscript and Zenodo record. The code is available strictly **as is**, and **no updates, bug fixes, enhancements, or maintenance will be performed on this repository**. For legal terms and liability limits, see [DISCLAIMER.md](DISCLAIMER.md) and [SECURITY.md](SECURITY.md).

dspant (Digital Signal Processing for Analysis Toolkit) is a Python package, with a Rust core, for processing
electrophysiological time series. It loads recordings lazily with Dask, so recordings larger than memory can be
filtered and analyzed, and it stores data and metadata in an open format based on Parquet and JSON (`.ant`).

This repository contains the code used in:

> Penaloza-Aponte JD, Dale EA.
> Invasive diaphragm electromyography data acquisition and analysis in rodents.
> *Biomedical Signal Processing and Control* (under revision).

## Contents

| Folder | Contents |
|---|---|
| `src/dspant/` | Core package: data nodes, processing engine, filters, envelopes (TKEO, moving RMS), spatial filtering, time-frequency transforms, input/output. |
| `rust/` | Rust implementations of performance-critical operations, built as `dspant._rs`. |
| `dspant_emgproc/` | EMG extension: activity (onset and offset) detection. |
| `paper_figures/` | Scripts that produce every figure of the manuscript and the values quoted in the figure legends (`img/`). |
| `docs/` | How to install, format data, convert recordings, process signals, and reproduce the figures. |

## Installation

Requires Python 3.12 or later, [uv](https://docs.astral.sh/uv/), and a Rust toolchain ([rustup](https://rustup.rs/)).

```bash
git clone <repository-url> dspant
cd dspant
uv sync --extra emgproc
```

`uv sync` builds the Rust extensions with maturin. See [docs/installation.md](docs/installation.md) for details and
optional extras.

## Data

The recordings used in the manuscript are not distributed with this repository. The figure scripts read data from the
folder set in `paper_figures/dataset_config.py`. Each recording must be in the `.ant` format
([docs/data-format.md](docs/data-format.md)); [docs/converting-data.md](docs/converting-data.md) shows how to convert
TDT tanks or any array-based recording. The figures in `paper_figures/img/` and their metrics files are the outputs of
the scripts on the original recordings.

## Quick start

```python
from dspant.engine import create_processing_node
from dspant.nodes import StreamNode
from dspant.processors.filters import FilterProcessor
from dspant.processors.filters.iir_filters import create_bandpass_filter, create_notch_filter

stream = StreamNode("path/to/recording/RawG.ant")
stream.load_metadata()
stream.load_data()

node = create_processing_node(stream)
node.add_processor(
    [
        FilterProcessor(filter_func=create_notch_filter(60, q=30, fs=stream.fs).get_filter_function(), overlap_samples=40),
        FilterProcessor(filter_func=create_bandpass_filter(20, 2000, fs=stream.fs, order=5).get_filter_function(), overlap_samples=40),
    ],
    group="filters",
)
filtered = node.process(group=["filters"])  # lazy Dask array (samples x channels)
```

More in [docs/processing-quickstart.md](docs/processing-quickstart.md).

## Citation

If you use this code, please cite the article above and this software ([CITATION.cff](CITATION.cff)).

## License and Disclaimer

Distributed under the MIT License ([LICENSE](LICENSE)).

The code is provided **"as is"** and **"as available"** without warranty of any kind. As an archived research record, no future updates or maintenance will be provided. The software is intended solely for scientific research and must not be used for clinical or medical purposes. Users bear full responsibility for validating outputs for their own research. See [DISCLAIMER.md](DISCLAIMER.md) and [SECURITY.md](SECURITY.md) for full terms and limitation of liability.
