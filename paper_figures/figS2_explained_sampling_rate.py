"""
/figS2_explained_sampling_rate.py
Author: jpenalozaa
Description: Supplementary figure S2. Effect of sampling rate on a recorded EMGdia burst.
One inspiratory burst from the baseline recording (25-02-26_9881-2_baseline, RawG, channel 0), filtered as in all
figures (60 Hz notch, Q = 30; 5th-order Butterworth bandpass 20-2000 Hz) at the recorded rate (24.4 kHz), is
resampled to 16 kHz and 5 kHz (FFT resampling, which removes everything above the new Nyquist frequency).

Panels (two columns; recorded rate grey, resampled rates overlaid in colour with transparency):
  A) the burst at the three rates.
  B) Welch power spectra (84 ms segments) up to 2.5 kHz, in dB relative to the peak of the recorded spectrum.
  C) ~5 ms around the largest motor unit action potential with every sample marked: a higher rate only
     shortens the sample period (41, 62.5, 200 us).
  D) 50 ms causal moving RMS at each rate (window converted from ms to samples for each rate): the band-limited
     burst, and therefore its envelope, is the same once the rate exceeds about 2.5 times the 2 kHz band limit.

Outputs: img/figS2_sampling_rate.png, img/figS2_sampling_rate_metrics.json
"""

# %%
import os
from pathlib import Path

import matplotlib.pyplot as plt
import mp_metrics as mpm
import mp_plotting_utils as mpu
import numpy as np
from dataset_config import DATA_DIR, FIGURE_DIR
from matplotlib.gridspec import GridSpec
from scipy import signal

from dspant.engine import create_processing_node
from dspant.nodes import StreamNode
from dspant.processors.filters import FilterProcessor
from dspant.processors.filters.iir_filters import create_bandpass_filter, create_notch_filter

mpu.set_publication_style()

CHANNEL = 0
SEGMENT_START_S = 5.0  # search window for a burst (same recording segment as Figures 6-8)
SEGMENT_S = 3.0
WINDOW_S = 0.6  # displayed window around the burst
EDGE_S = 0.2  # extra signal on each side, discarded after resampling (FFT edge effects)
RMS_WINDOW_MS = 50.0
WELCH_SEGMENT_MS = 84.0
ZOOM_MS = 5.0
RATES_HZ = (None, 16000.0, 5000.0)  # None = recorded rate

# %%
stream_emg = StreamNode(str(DATA_DIR.joinpath("25-02-26_9881-2_baseline", "RawG.ant")))
stream_emg.load_metadata()
stream_emg.load_data()
FS = float(stream_emg.fs)

processor = create_processing_node(stream_emg)
processor.add_processor(
    [
        FilterProcessor(filter_func=create_notch_filter(60, q=30, fs=FS).get_filter_function(), overlap_samples=40),
        FilterProcessor(filter_func=create_bandpass_filter(20, 2000, fs=FS, order=5).get_filter_function(), overlap_samples=40),
    ],
    group="filters",
)
filtered = processor.process(group=["filters"])
s0, n = int(SEGMENT_START_S * FS), int(SEGMENT_S * FS)
seg = np.asarray(filtered[s0 : s0 + n, CHANNEL].compute(), dtype=float)


def moving_rms(x: np.ndarray, fs: float, window_ms: float) -> np.ndarray:
    """Causal moving RMS; the window is set in ms and converted to samples for this rate."""
    w = int(round(window_ms * 1e-3 * fs))
    return np.sqrt(np.convolve(x**2, np.ones(w) / w, mode="full")[: len(x)])


# locate the strongest burst in the search segment (largest 50 ms RMS), then take a window around it
center = int(np.argmax(moving_rms(seg, FS, RMS_WINDOW_MS)[int(EDGE_S * FS) : -int(EDGE_S * FS)])) + int(EDGE_S * FS)
half, edge = int(WINDOW_S / 2 * FS), int(EDGE_S * FS)
lo, hi = max(0, center - half - edge), min(len(seg), center + half + edge)
burst = seg[lo:hi]

traces = {}
for rate in RATES_HZ:
    fs = FS if rate is None else rate
    y = burst if rate is None else signal.resample(burst, int(round(len(burst) * fs / FS)))
    k = int(round(EDGE_S * fs))
    y = y[k:-k]  # drop the edges used to absorb FFT wrap-around
    traces[fs] = {"t": np.arange(len(y)) / fs, "x": y, "rms": moving_rms(y, fs, RMS_WINDOW_MS)}

# envelope agreement: interpolate each envelope onto the recorded time base (excluding the first window)
ref = traces[FS]
start = RMS_WINDOW_MS * 1e-3
mask = ref["t"] >= start
metrics = {"fs_recorded_hz": FS, "rates_hz": list(traces), "window_s": WINDOW_S, "rms_window_ms": RMS_WINDOW_MS}
for fs, tr in traces.items():
    if fs == FS:
        continue
    env = np.interp(ref["t"][mask], tr["t"], tr["rms"])
    diff = np.abs(env - ref["rms"][mask]).max() / ref["rms"][mask].max() * 100
    metrics[f"rms_envelope_max_diff_pct_{fs:.0f}Hz"] = float(diff)
metrics["sample_period_us"] = {f"{fs:.0f}": float(1e6 / fs) for fs in traces}
metrics["rms_window_samples"] = {f"{fs:.0f}": int(round(RMS_WINDOW_MS * 1e-3 * fs)) for fs in traces}

# largest action potential for the zoom
peak_t = ref["t"][np.argmax(np.abs(ref["x"]))]
z0, z1 = peak_t - ZOOM_MS / 2e3, peak_t + ZOOM_MS / 2e3
for fs, tr in traces.items():
    m = (tr["t"] >= z0) & (tr["t"] <= z1)
    metrics[f"zoom_peak_abs_{fs:.0f}Hz"] = float(np.abs(tr["x"][m]).max())
mpm.save_metrics(metrics, mpm.figure_dir() / "figS2_sampling_rate_metrics.json")
for k_, v_ in metrics.items():
    print(f"{k_}: {v_}")

# %%
# Sizes as in the other manuscript figures (e.g. fig08_explained_metrics_v2.py): 7 in wide, FONT_SIZE = 16
plt.rcParams["mathtext.default"] = "regular"  # subscripts in the same font as the text
FONT_SIZE = 16
SUBTITLE_SIZE = int(FONT_SIZE * 0.8)  # 12: panel titles and panel letters
AXIS_LABEL_SIZE = int(FONT_SIZE * 0.7)  # 11
TICK_SIZE = int(FONT_SIZE * 0.7)  # 11
LEGEND_SIZE = int(FONT_SIZE * 0.7)  # 11
TXT = dict(title_fontsize=SUBTITLE_SIZE, label_fontsize=AXIS_LABEL_SIZE, tick_fontsize=TICK_SIZE)
LEG = LEGEND_SIZE
# original (recorded) signal in grey; resampled versions overlaid in colour with transparency
style = {
    FS: dict(color=mpu.COLORS["gray"], label="24.4 kHz (recorded, 41 μs)", alpha=1.0, lw=1.6, ms=2.5),
    16000.0: dict(color=mpu.COLORS["blue"], label="16 kHz (62.5 μs)", alpha=0.5, lw=0.6, ms=3),
    5000.0: dict(color=mpu.COLORS["orange"], label="5 kHz (200 μs)", alpha=0.5, lw=0.6, ms=4),
}
FIG_W, FIG_H = 7.0, 7.0
fig = plt.figure(figsize=(FIG_W, FIG_H))


def axes_in(x, y, w, h):
    """Axes placed in inches from the bottom-left corner, so every gap is set explicitly."""
    return fig.add_axes([x / FIG_W, y / FIG_H, w / FIG_W, h / FIG_H])


# two columns: left = signal (time domain), right = spectrum / envelope
LEFT, WIDTH, GAP = 0.85, 6.0, 1.0
HALF = (WIDTH - GAP) / 2
COL2 = LEFT + HALF + GAP
ax_a = axes_in(LEFT, 4.35, HALF, 2.15)  # EMG at the three rates
ax_b = axes_in(COL2, 4.35, HALF, 2.15)  # power spectra
ax_c = axes_in(LEFT, 1.25, HALF, 2.05)  # samples around one action potential
ax_d = axes_in(COL2, 1.25, HALF, 2.05)  # moving RMS envelopes

# A: one burst, original in grey, resampled versions on top with transparency
for fs, tr in traces.items():
    ax_a.plot(tr["t"] * 1e3, tr["x"], color=style[fs]["color"], lw=style[fs]["lw"], alpha=style[fs]["alpha"])
ax_a.axvspan(z0 * 1e3, z1 * 1e3, color=mpu.COLORS["yellow"], alpha=0.45)  # region zoomed in C
mpu.format_axis(ax_a, title="EMG$_{dia}$ Burst", xlabel="Time [ms]", ylabel="Amplitude", xlim=(0, ref["t"][-1] * 1e3), **TXT)

# B: power spectra of the same signals, in dB relative to the peak of the recorded spectrum (as Figures 1-2)
spectra = {fs: signal.welch(tr["x"], fs=fs, nperseg=int(round(WELCH_SEGMENT_MS * 1e-3 * fs))) for fs, tr in traces.items()}
p_ref = spectra[FS][1].max()  # one reference for all rates, so differences between them are kept
for fs, (f, pxx) in spectra.items():
    keep = f <= 2500
    ax_b.plot(f[keep], 10 * np.log10(pxx[keep] / p_ref), color=style[fs]["color"], lw=2.2 if fs == FS else 1.2,
              ls="-" if fs == FS else "--", alpha=1.0 if fs == FS else 0.8)
h_lim = ax_b.axvline(2000, color=mpu.COLORS["red"], ls=":", lw=1.2, label="Band limit (2 kHz)")
mpu.format_axis(ax_b, title="Power Spectrum", xlabel="Frequency [Hz]", ylabel="Power [dB]", **TXT)

# C: samples around the largest action potential (yellow region in A)
for fs, tr in traces.items():
    m = (tr["t"] >= z0) & (tr["t"] <= z1)
    ax_c.plot((tr["t"][m] - peak_t) * 1e3, tr["x"][m], "-o", color=style[fs]["color"], lw=1.0, ms=style[fs]["ms"],
              alpha=max(style[fs]["alpha"], 0.8), mfc="none" if fs == 5000.0 else style[fs]["color"])
mpu.format_axis(ax_c, title="Action Potential Samples", xlabel="Time [ms]", ylabel="Amplitude", **TXT)

# D: 50 ms moving RMS at each rate (window converted from ms to samples for each rate)
for fs, tr in traces.items():
    ax_d.plot(tr["t"] * 1e3, tr["rms"], color=style[fs]["color"], lw=1.8 if fs == FS else 1.3,
              ls="-" if fs == FS else "--", alpha=1.0)
mpu.format_axis(ax_d, title="Moving RMS (50 ms)", xlabel="Time [ms]", ylabel="Amplitude", xlim=(0, ref["t"][-1] * 1e3), **TXT)

# one legend for all panels: the colour identifies the sampling rate (sample period in brackets)
handles = [plt.Line2D([], [], color=style[fs]["color"], lw=2, alpha=max(style[fs]["alpha"], 0.8), label=style[fs]["label"]) for fs in traces]
fig.legend(handles=handles + [h_lim], fontsize=LEG, ncol=2, frameon=False, loc="center",
           bbox_to_anchor=((LEFT + WIDTH / 2) / FIG_W, 0.35 / FIG_H), columnspacing=1.2, handlelength=1.8)

for ax in (ax_a, ax_c, ax_d):
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    ax.yaxis.get_offset_text().set_fontsize(TICK_SIZE)
ax_b.ticklabel_format(axis="x", style="sci", scilimits=(0, 0), useMathText=True)
ax_b.xaxis.get_offset_text().set_fontsize(TICK_SIZE)
# letters left of the y-axis label so they do not sit on the x10^n scale text (offset is a fraction of panel width)
for ax, label in ((ax_a, "A"), (ax_b, "B"), (ax_c, "C"), (ax_d, "D")):
    mpu.add_panel_label(ax, label, x_offset_factor=0.24, y_offset_factor=0.01, fontsize=SUBTITLE_SIZE)

FIGURE_PATH = mpm.figure_dir().joinpath("figS2_sampling_rate.png")
mpu.save_figure(fig, FIGURE_PATH, dpi=600)
print(f"Figure saved to: {FIGURE_PATH}")
