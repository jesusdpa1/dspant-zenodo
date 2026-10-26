# Converting data to `.ant`

## From a TDT tank (Tucker-Davis Technologies)

`convert_tdt_to_ant` reads a TDT block with the `tdt` package and writes one `.ant` folder per stream and per epoc
(event channel).

```python
from dspant.io.exporters import convert_tdt_to_ant

out = convert_tdt_to_ant(
    "path/to/Tank/Block-1",     # TDT block folder
    output_path="path/to/data", # base folder for the converted data
    stream_names=["RawG"],      # None converts all streams
    epoc_names=None,            # None converts all epocs
)
print(out)  # path/to/data/Tank/drv_Block-1/, which contains RawG.ant/ and one .ant folder per epoc
```

Without `output_path`, the converted data are written inside the block folder (`Block-1/drv_Block-1/`).

The sampling rate, channel information, and TDT-specific fields are written to the metadata file automatically.

## From any array (NumPy or Dask)

Any recording that can be read into an array (samples x channels) can be saved as `.ant` with `save_to_ant`. This
covers formats such as Spike2, Intan, Open Ephys, or Blackrock, which can be read with
[neo](https://neo.readthedocs.io/) (installed with dspant), as well as MATLAB, CSV, or HDF5 files.

```python
import numpy as np
from dspant.io.exporters.array2ant import save_to_ant

fs = 24414.0625                         # sampling rate in Hz
data = np.load("my_recording.npy")       # shape (samples, channels)

path = save_to_ant(
    data,
    output_path="path/to/data/my_session/RawG.ant",
    fs=fs,
    name="RawG",
    metadata={"other": {"units": "V", "subject": "rat-01"}},  # optional
)
```

For several streams of one session (for example EMG and pressure at different rates), `save_to_ant_multi` takes a
dictionary of arrays and a dictionary of sampling rates.

### Example: Spike2 (`.smr` / `.smrx`) with neo

```python
import numpy as np
from neo.io import Spike2IO
from dspant.io.exporters.array2ant import save_to_ant

block = Spike2IO("recording.smrx").read_block()
signal = block.segments[0].analogsignals[0]          # first group of channels
data = np.asarray(signal.magnitude, dtype=np.float32)  # samples x channels
save_to_ant(data, output_path="data/session/emg.ant", fs=float(signal.sampling_rate), name="emg")
```

## Checking the result

```python
from dspant.nodes import StreamNode

stream = StreamNode("path/to/data/my_session/RawG.ant")
stream.load_metadata()
stream.load_data()
print(stream.fs, stream.data.shape)
```

## Units and data type

Store the signal in physical units (for example volts) as 32-bit floats. The processing and the figure scripts
assume that amplitudes are in the units of the original recording; no scaling is applied when loading.
