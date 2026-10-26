"""
/dataset_config.py
Description: Where the figure scripts find their input data and write their outputs.

Edit DATA_DIR below to point to the folder that holds your recordings. Nothing else needs to change.

Expected layout (one folder per recording, one .ant folder per stream; see docs/data-format.md):

    DATA_DIR/
        25-02-26_9881-2_baseline/RawG.ant              Figures 4-8 (scripts fig04-fig08), S1, S2
        noisy_recording/noisy_recording.ant           Figure 3 (fig03)
        sample_ventilator_trace/emg_l.ant             Figure 10 (fig09, neural trigger)
        sample_ventilator_trace/emg_r.ant
        sample_ventilator_trace/insp.ant
        25-02-21_15-40-17_stim/RawG.ant               Figure 11 (fig10, closed-loop stimulation)
        25-02-21_15-40-17_stim/MonA.ant

Figures 1 and 2 use synthetic signals and need no data.

Each stream must be in the dspant .ant format: a folder <name>.ant/ containing
data_<name>.parquet (samples x channels) and metadata_<name>.json (sampling rate, channel names, ...).
docs/converting-data.md shows how to create .ant streams from TDT tanks or from NumPy/Dask arrays.
"""

import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# Folder that holds the recordings (edit this line).
DATA_DIR = REPO / "data"

# Where figures (PNG) and legend metrics (JSON) are written.
FIGURE_DIR = HERE / "img"

# Cache for expensive intermediate results (time-frequency transforms); safe to delete.
CACHE_DIR = REPO / "cache"

if not DATA_DIR.is_dir():
    warnings.warn(
        f"DATA_DIR does not exist: {DATA_DIR}. Set DATA_DIR in paper_figures/dataset_config.py "
        "(see docs/data-format.md). Figures 1 and 2 run without data.",
        stacklevel=2,
    )
