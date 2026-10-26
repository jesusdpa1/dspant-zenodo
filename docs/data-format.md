# Data format (`.ant`)

dspant reads and writes recordings in the `.ant` format. A `.ant` stream is a folder with two files:

```
RawG.ant/
    data_RawG.parquet       signal: one row per sample, one column per channel
    metadata_RawG.json      sampling rate, channel names, shape, and any other information
```

dspant finds the two files by their prefixes (`data_*.parquet` and `metadata_*.json`), so each `.ant` folder must hold
exactly one of each; the rest of the name is free (the TDT converter, for example, adds the time segment:
`data_RawG_t0_0-300_0.parquet`).

Parquet is an open, compressed, column-based file format that can be read without loading the whole file, so long
recordings can be processed lazily. Any tool that reads Parquet (Python, R, MATLAB) can open the data file directly.

## Metadata

`metadata_<name>.json` has two sections:

- `base`: the fields dspant needs:
  - `fs`: sampling rate in Hz (for example `24414.0625`);
  - `number_of_samples`, `data_shape`: number of samples and `[samples, channels]`;
  - `channel_numbers`, `channel_names`, `channel_types`;
  - `name`: stream name.
- `other`: anything else from the acquisition system (gain, units, device, subject, date, ...).

Files written by the converters in [converting-data.md](converting-data.md) already have this structure.

## Recordings and streams

A recording session is a folder that holds one `.ant` folder per stream, for example an EMG stream and an inspiratory
pressure stream recorded at the same time:

```
sample_ventilator_trace/
    emg_l.ant/
    emg_r.ant/
    insp.ant/
```

## Loading a stream

```python
from dspant.nodes import StreamNode

stream = StreamNode("path/to/sample_ventilator_trace/emg_l.ant")
stream.load_metadata()   # reads metadata_emg_l.json; stream.fs holds the sampling rate
stream.load_data()       # opens data_emg_l.parquet lazily as a Dask array
x = stream.data          # samples x channels
```

## Data for the manuscript figures

The figure scripts expect the recordings listed in `paper_figures/dataset_config.py`, under the folder set there as
`DATA_DIR`. The original recordings are not distributed with this repository. To run the scripts on your own data,
convert each recording to `.ant`, keep the folder and stream names listed in `dataset_config.py` (or edit the paths in
the scripts), and set `DATA_DIR`.
