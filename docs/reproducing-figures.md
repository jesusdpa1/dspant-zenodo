# Reproducing the manuscript figures

`paper_figures/` holds one script per figure (`figNN_explained_*.py`) and, for the figures with quantitative legends,
a script that computes the legend values (`figNN_legend_metrics.py`). Outputs go to `paper_figures/img/`: the figure
as PNG (600 dpi) and the legend values as JSON.

## Setup

1. Install dspant with the EMG extension ([installation.md](installation.md)).
2. Put the recordings in `.ant` format under one folder and set `DATA_DIR` in `paper_figures/dataset_config.py`
   ([data-format.md](data-format.md)).
3. Run the scripts from inside `paper_figures/`, so that the shared helpers (`mp_plotting_utils.py`, `mp_metrics.py`,
   `mp_cache.py`, `dataset_config.py`) are found:

```bash
cd paper_figures
MPLBACKEND=Agg uv run python fig01_explained_iir-vs-fir.py
```

## Scripts and printed figure numbers

The script numbers follow the original submission. From Figure 7 on, the printed numbers are one higher, because the
ECG/EMG separation figure was added as Figure 7.

| Printed figure | Figure script | Legend metrics | Data |
|---|---|---|---|
| 1 | `fig01_explained_iir-vs-fir.py` | `fig01_fig02_legend_metrics.py` | synthetic |
| 2 | `fig02_explained_combined_filters-phase-delay.py` | `fig01_fig02_legend_metrics.py` | synthetic |
| 3 | `fig03_explained_noise_filters_ffc.py` | `fig03_legend_metrics.py` | `noisy_recording` |
| 4 | `fig04_explained_template-subtraction.py` | `fig04_legend_metrics.py` | baseline |
| 5 | `fig05_explained_common_reference.py` | `fig05_legend_metrics.py` | baseline (32 channels) |
| 6 | `fig06_explained_cwt_stft.py` | (in Figure 7's metrics) | baseline |
| 7 | `fig06b_explained_ecg_emg_separation.py` | `fig06b_legend_metrics.py` | baseline |
| 8 | `fig07_explained_combined_envelopes.py` | `fig07_legend_metrics.py` | baseline |
| 9 | `fig08_explained_metrics_v2.py` | none (definitional figure) | baseline |
| 10 | `fig09_explained_ventilatory_simplified.py` | `fig09_legend_metrics.py` | `sample_ventilator_trace` |
| 11 | `fig10_explained_stim.py` | `fig10_legend_metrics.py` | stimulation recording |
| S1 | `figS_explained_rms75.py` | written by the figure script | baseline |
| S2 | `figS2_explained_sampling_rate.py` | written by the figure script | baseline |

The legend-metrics scripts run the corresponding figure script and then compute the values quoted in the legend, so
every number in a legend can be traced to a key in its JSON file.

## Run time and memory

Most scripts finish in under a minute. Figures 6 and 7 compute continuous wavelet transforms of long segments and need
about 10 GB of free memory; their transforms are cached in `cache/` (set in `dataset_config.py`) and reused when the
parameters have not changed. Computation times reported in the Figure 3 legend depend on the machine.
