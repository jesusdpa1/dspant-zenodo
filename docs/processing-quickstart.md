# Processing quick start

The example processes one EMG stream the way the manuscript figures do: notch and bandpass filtering, a TKEO envelope,
onset detection, and RMS75 (the moving RMS 75 ms after each onset). All time parameters are set in milliseconds and
converted to samples with the sampling rate of the recording.

```python
import dask.array as da
import numpy as np

from dspant.engine import create_processing_node
from dspant.nodes import StreamNode
from dspant.processors.basic.energy_rs import create_tkeo_envelope_rs
from dspant.processors.filters import FilterProcessor
from dspant.processors.filters.fir_filters import create_moving_rms
from dspant.processors.filters.iir_filters import create_bandpass_filter, create_lowpass_filter, create_notch_filter
from dspant_emgproc.processors.activity_detection.single_threshold import create_single_threshold_detector

# 1. Load the stream (lazy)
stream = StreamNode("path/to/recording/RawG.ant")
stream.load_metadata()
stream.load_data()
fs = float(stream.fs)

# 2. Notch (60 Hz, Q = 30) and bandpass (20-2000 Hz, 5th-order Butterworth), zero phase
node = create_processing_node(stream)
node.add_processor(
    [
        FilterProcessor(filter_func=create_notch_filter(60, q=30, fs=fs).get_filter_function(), overlap_samples=40),
        FilterProcessor(filter_func=create_bandpass_filter(20, 2000, fs=fs, order=5).get_filter_function(), overlap_samples=40),
    ],
    group="filters",
)
filtered = node.process(group=["filters"])

# work on one channel and a 30 s segment
x = np.asarray(filtered[int(5 * fs) : int(35 * fs), 0:1].compute())
x_da = da.from_array(x, chunks=(len(x), 1))

# 3. TKEO envelope (modified TKEO + 20 Hz lowpass)
tkeo = create_tkeo_envelope_rs("modified", rectify=False, smooth=False)
lowpass = FilterProcessor(filter_func=create_lowpass_filter(20, fs).get_filter_function(), overlap_samples=40)
envelope = lowpass.process(tkeo.process(x_da), fs=fs)

# 4. Onsets: envelope above a threshold for at least 20 ms, at least 200 ms between onsets
detector = create_single_threshold_detector(
    threshold_method="percent_max", threshold_value=20,
    min_contraction_duration=0.020, refractory_period=0.200,
)
events = detector.process(envelope, fs=fs).compute()   # onset_idx, offset_idx per burst

# 5. RMS75: causal 50 ms moving RMS, read 75 ms after each onset
rms = create_moving_rms(window_size=round(0.050 * fs), center=False).process(x_da).compute()[:, 0]
delay = round(0.075 * fs)
onsets = events["onset_idx"]
rms75 = rms[onsets[onsets + delay < len(rms)] + delay]
print(len(onsets), "bursts; mean RMS75 =", rms75.mean())
```

The manuscript's supplementary material gives each step in more detail, including a threshold based on the expiratory
baseline ($T_{on} = \mu_{exp} + k\,\sigma_{exp}$) and the 70%-of-peak offset searched backward from the end of each
burst. `paper_figures/figS_explained_rms75.py` implements both.
