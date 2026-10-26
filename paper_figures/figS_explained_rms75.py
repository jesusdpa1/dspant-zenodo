"""
/figS_explained_rms75.py
Author: jpenalozaa
Description: Supplementary figure S1. Burst detection and RMS75 (RMS amplitude 75 ms after burst onset;
Seven et al., 2014) computed with dspant on the baseline recording used in Figures 6-8
(25-02-26_9881-2_baseline, RawG, channel 0, 5-35 s).

Pipeline (all time parameters are given in ms and converted to samples with the recording's sampling rate):
  1. Notch 60 Hz (Q = 30) + 5th-order Butterworth bandpass 20-2000 Hz (same as all figures).
  2. Onset detection on the TKEO envelope (modified TKEO + 20 Hz lowpass; TKEO attenuates the ECG, Figure 8)
     with dspant's SingleThresholdDetector, using the rule of Section 4.4 (Hodges & Bui, 1996):
     T_on = mu_exp + k * sigma_exp of the expiratory baseline, envelope above T_on for >= MIN_DURATION_MS.
     Offset (end of T_I, start of T_E; Section 4.4, Jonkman et al., 2024): first sample after the burst peak at
     which the envelope falls to 70% of the peak. The peak is searched between onset and the return below T_on.
     T_I = onset -> offset, T_E = offset -> next onset, T_TOT = onset -> next onset, duty cycle = T_I / T_TOT.
     mu_exp and sigma_exp are pooled over all expiratory samples: everything between the bursts of a first
     detection pass (percent of maximum), excluding BASELINE_MARGIN_MS around each burst.
  3. Moving RMS of the filtered EMG (dspant create_moving_rms), causal window RMS_WINDOW_MS.
  4. RMS75 = moving RMS value at onset + RMS75_DELAY_MS. With a causal 50 ms window this is the RMS of the
     signal from 25 to 75 ms after onset.

Outputs: img/figS_rms75.png, img/figS_rms75_metrics.json
"""

# %%
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import dask.array as da
import matplotlib.pyplot as plt
import mp_metrics as mpm
import mp_plotting_utils as mpu
import numpy as np
from dataset_config import DATA_DIR, FIGURE_DIR
from matplotlib.gridspec import GridSpec

from dspant.engine import create_processing_node
from dspant.nodes import StreamNode
from dspant.processors.basic.energy_rs import create_tkeo_envelope_rs
from dspant.processors.filters import FilterProcessor
from dspant.processors.filters.fir_filters import create_moving_rms
from dspant.processors.filters.iir_filters import (
    create_bandpass_filter,
    create_lowpass_filter,
    create_notch_filter,
)
from dspant_emgproc.processors.activity_detection.single_threshold import (
    create_single_threshold_detector,
)

mpu.set_publication_style()


@dataclass(frozen=True)
class Params:
    channel: int = 0
    start_s: float = 5.0
    duration_s: float = 30.0
    rms_window_ms: float = 50.0  # Seven et al. 2014: 50 ms RMS window
    rms_center: bool = False  # causal (past-only) window, as in Figure 8
    rms75_delay_ms: float = 75.0
    k: float = 3.0  # T_on = mu_exp + k * sigma_exp, k in [2, 3]
    min_duration_ms: float = 20.0  # minimum time above T_on (15-30 ms)
    offset_fraction: float = 0.70  # offset = envelope falls to 70% of the burst peak (Jonkman et al., 2024)
    refractory_ms: float = 200.0  # minimum time between onsets
    first_pass_percent_max: float = 20.0
    baseline_margin_ms: float = 100.0
    tkeo_lowpass_hz: float = 20.0
    overview_s: float = 10.0  # length of the overview panel


P = Params()


def ms_to_samples(ms: float, fs: float) -> int:
    return int(round(ms * 1e-3 * fs))


# %%
# Load and filter (same filters as all figures)
stream_emg = StreamNode(str(DATA_DIR.joinpath("25-02-26_9881-2_baseline", "RawG.ant")))
stream_emg.load_metadata()
stream_emg.load_data()
FS = float(stream_emg.fs)

notch_filter = create_notch_filter(60, q=30, fs=FS)
bandpass_filter = create_bandpass_filter(20, 2000, fs=FS, order=5)
processor_emg = create_processing_node(stream_emg)
processor_emg.add_processor(
    [
        FilterProcessor(filter_func=notch_filter.get_filter_function(), overlap_samples=40),
        FilterProcessor(filter_func=bandpass_filter.get_filter_function(), overlap_samples=40),
    ],
    group="filters",
)
filter_data = processor_emg.process(group=["filters"])

s0 = int(P.start_s * FS)
n = int(P.duration_s * FS)
x = np.asarray(filter_data[s0 : s0 + n, P.channel : P.channel + 1].compute())  # (n, 1)
# single chunk: the detector's baseline window is relative to the chunk start
x_da = da.from_array(x, chunks=(n, 1))

# %%
# Onset detection on the TKEO envelope
tkeo = create_tkeo_envelope_rs("modified", rectify=False, smooth=False)
tkeo_lowpass = FilterProcessor(
    filter_func=create_lowpass_filter(P.tkeo_lowpass_hz, FS).get_filter_function(), overlap_samples=40
)
tkeo_env = tkeo_lowpass.process(tkeo.process(x_da), fs=FS).compute()[:, 0]
tkeo_env_da = da.from_array(tkeo_env[:, None], chunks=(len(tkeo_env), 1))


def detect(method: str, value: float, baseline_window=None) -> np.ndarray:
    detector = create_single_threshold_detector(
        threshold_method=method,
        threshold_value=value,
        min_contraction_duration=P.min_duration_ms * 1e-3,
        refractory_period=P.refractory_ms * 1e-3,
        baseline_window=baseline_window,
    )
    events = detector.process(tkeo_env_da, fs=FS).compute()
    return events, detector.thresholds[0]


first_pass, _ = detect("percent_max", P.first_pass_percent_max)
margin = ms_to_samples(P.baseline_margin_ms, FS)
expiration = np.zeros(len(tkeo_env), bool)
expiration[first_pass["onset_idx"][0] : first_pass["offset_idx"][-1]] = True
for e in first_pass:
    expiration[max(0, e["onset_idx"] - margin) : e["offset_idx"] + margin] = False
mu_exp, sigma_exp = tkeo_env[expiration].mean(), tkeo_env[expiration].std()
events, t_on = detect("absolute", mu_exp + P.k * sigma_exp)

# %%
# Moving RMS and RMS75
rms_window = ms_to_samples(P.rms_window_ms, FS)
rms75_delay = ms_to_samples(P.rms75_delay_ms, FS)
min_dur = ms_to_samples(P.min_duration_ms, FS)
rms_env = create_moving_rms(window_size=rms_window, center=P.rms_center).process(x_da).compute()[:, 0]

keep = [e for e in events if e["onset_idx"] + rms75_delay < len(rms_env)]
onsets = np.array([e["onset_idx"] for e in keep])


def offset_70(env: np.ndarray, pk: int, end: int) -> int:
    """Offset (end of T_I): the final fall below 70% of the burst peak before the burst ends.

    Searched backward from the burst end to the peak: the offset is the sample after the last one at or above
    70% of the peak. A forward search (first sample below 70% after the peak) stops at a brief dip between the
    humps of a multi-peaked burst ("double dipping"), which shortens T_I and starts T_E too early.
    """
    above = np.nonzero(env[pk : end + 1] >= P.offset_fraction * env[pk])[0]
    return pk + int(above[-1]) + 1


def offset_70_forward(env: np.ndarray, pk: int) -> int:
    """First sample after the peak below 70% of it; kept only to count the bursts where it stops too early."""
    return pk + int(np.argmax(env[pk:] <= P.offset_fraction * env[pk]))


thr_offsets = np.array([e["offset_idx"] for e in keep])  # return below T_on = end of the burst
peaks = np.array([on + np.argmax(tkeo_env[on : off + 1]) for on, off in zip(onsets, thr_offsets)])
offsets = np.array([offset_70(tkeo_env, pk, off) for pk, off in zip(peaks, thr_offsets)])
offsets_fwd = np.array([offset_70_forward(tkeo_env, pk) for pk in peaks])
# respiratory timing (Section 5.1): T_I, T_E, T_TOT and duty cycle, in s
t_i = (offsets - onsets) / FS
t_tot = np.diff(onsets) / FS
t_e = (onsets[1:] - offsets[:-1]) / FS
duty = t_i[:-1] / t_tot
# the same 70% rule on the moving RMS envelope (peak searched from onset to the T_on return plus one RMS window,
# because the causal RMS lags the signal), to show how the envelope choice changes T_I
rms_peaks = np.array([on + np.argmax(rms_env[on : off + rms_window]) for on, off in zip(onsets, thr_offsets)])
rms_ends = thr_offsets + rms_window  # the causal RMS ends one window after the T_on return
rms_offsets = np.array([offset_70(rms_env, pk, end) for pk, end in zip(rms_peaks, rms_ends)])
rms_offsets_fwd = np.array([offset_70_forward(rms_env, pk) for pk in rms_peaks])
t_i_rms = (rms_offsets - onsets) / FS
tkeo75 = tkeo_env[onsets + rms75_delay]  # TKEO envelope 75 ms after onset, for comparison with RMS75
rms75 = rms_env[onsets + rms75_delay]
peak_rms = np.array([rms_env[o : o + int(1.0 * FS)].max() for o in onsets])
if P.rms_center:
    win_lo, win_hi = rms75_delay - rms_window // 2, rms75_delay + rms_window // 2
else:
    win_lo, win_hi = rms75_delay - rms_window + 1, rms75_delay

# Independent check: RMS squares each sample, so it is the same for the filtered and the rectified signal
# (x^2 = |x|^2). Recompute the causal moving RMS from the rectified signal with numpy and compare.
rect = np.abs(x[:, 0]).astype(float)
check_env = np.sqrt(np.convolve(rect**2, np.ones(rms_window) / rms_window, mode="full")[: len(rect)])
steady = slice(rms_window, None)  # skip the first window (start-up of the causal average)
env_err = float(np.max(np.abs(check_env[steady] - rms_env[steady])) / np.max(rms_env[steady]) * 100)
rms75_err = float(np.max(np.abs(check_env[onsets + rms75_delay] - rms75) / rms75) * 100)
print(f"RMS check (numpy, rectified input) vs dspant: max envelope diff {env_err:.4f}% of peak; max RMS75 diff {rms75_err:.4f}%")

metrics = {
    "params": asdict(P),
    "fs_hz": FS,
    "samples": {"rms_window": rms_window, "rms75_delay": rms75_delay, "min_duration": min_dur},
    "rms_window_relative_to_onset_ms": [win_lo / FS * 1e3, win_hi / FS * 1e3],
    "n_bursts_first_pass": int(len(first_pass)),
    "expiration_fraction": float(expiration.mean()),
    "mu_exp": float(mu_exp),
    "sigma_exp": float(sigma_exp),
    "t_on": float(t_on),
    "n_bursts": int(len(onsets)),
    **{f"{name}_s": {"mean": float(v.mean()), "sd": float(v.std(ddof=1))} for name, v in (("t_i", t_i), ("t_e", t_e), ("t_tot", t_tot))},
    "duty_cycle": {"mean": float(duty.mean()), "sd": float(duty.std(ddof=1))},
    "t_i_rms_envelope_s": {"mean": float(t_i_rms.mean()), "sd": float(t_i_rms.std(ddof=1))},
    "t_i_rms_minus_tkeo_ms": {"mean": float((t_i_rms - t_i).mean() * 1e3), "sd": float((t_i_rms - t_i).std(ddof=1) * 1e3)},
    "tkeo75_cv_pct": float(tkeo75.std(ddof=1) / tkeo75.mean() * 100),
    # double dipping: bursts where the forward search stops at a dip before the final fall below 70%
    **{f"forward_search_early_{name}": {
        "n_bursts": int((fwd < bwd).sum()),
        "t_i_shortened_ms": [float(v) for v in np.round((bwd - fwd)[fwd < bwd] / FS * 1e3, 1)],
    } for name, fwd, bwd in (("tkeo", offsets_fwd, offsets), ("rms", rms_offsets_fwd, rms_offsets))},
    "corr_rms75_tkeo75": float(np.corrcoef(rms75, tkeo75)[0, 1]),
    "rms75_mean": float(rms75.mean()),
    "rms75_sd": float(rms75.std(ddof=1)),
    "rms75_cv_pct": float(rms75.std(ddof=1) / rms75.mean() * 100),
    "rms75_over_peak_rms_mean": float((rms75 / peak_rms).mean()),
    "rms_check_rectified_numpy_max_diff_pct": {"envelope": env_err, "rms75": rms75_err},
}
mpm.save_metrics(metrics, mpm.figure_dir() / "figS_rms75_metrics.json")
for k_, v_ in metrics.items():
    print(f"{k_}: {v_}")

# %%
# Figure S1
#   A) filtered EMG overview (first 10 s), the breath shown in C and D highlighted
#   B) TKEO and moving RMS envelopes, each normalized to its maximum, overlaid: onsets and 70% offsets of each
#   C) one breath, TKEO (normalized as in B): threshold, onset, peak, 70% offset, T_I / T_E / T_TOT
#   D) the same breath, moving RMS (normalized as in B): RMS75 and the same timing rule on this envelope
#   E) envelope amplitude 75 ms after onset for every burst, from each envelope, as % of its mean amplitude
# Colour code for the whole figure: EMG grey, TKEO orange, moving RMS blue, onset green, threshold red.
# Sizes as in the other manuscript figures (e.g. fig08_explained_metrics_v2.py): 7 in wide, FONT_SIZE = 16
plt.rcParams["mathtext.default"] = "regular"  # subscripts in the same font as the text
FONT_SIZE = 16
SUBTITLE_SIZE = int(FONT_SIZE * 0.8)  # 12: panel titles and panel letters
AXIS_LABEL_SIZE = int(FONT_SIZE * 0.7)  # 11
TICK_SIZE = int(FONT_SIZE * 0.7)  # 11
LEGEND_SIZE = int(FONT_SIZE * 0.7)  # 11
TXT = dict(title_fontsize=SUBTITLE_SIZE, label_fontsize=AXIS_LABEL_SIZE, tick_fontsize=TICK_SIZE)
LEG = LEGEND_SIZE
C_EMG, C_TKEO, C_RMS = mpu.COLORS["gray"], mpu.COLORS["orange"], mpu.COLORS["blue"]
C_ON, C_TH, C_TXT = mpu.COLORS["green"], mpu.COLORS["red"], mpu.COLORS["primary"]
t = np.arange(n) / FS
FIG_W, FIG_H = 7.0, 10.3
fig = plt.figure(figsize=(FIG_W, FIG_H))


def axes_in(x, y, w, h):
    """Axes placed in inches from the bottom-left corner, so every gap is set explicitly."""
    return fig.add_axes([x / FIG_W, y / FIG_H, w / FIG_W, h / FIG_H])


LEFT, WIDTH, GAP = 0.85, 6.0, 0.95  # left margin, plot width, gap between C and D (room for D's y label)
HALF = (WIDTH - GAP) / 2
ax_a = axes_in(LEFT, 8.9, WIDTH, 1.0)  # EMG; shares the time axis with B
ax_b = axes_in(LEFT, 7.55, WIDTH, 1.15)  # normalized envelopes, same time axis as A
ax_c = axes_in(LEFT, 4.35, HALF, 2.2)  # titles + x10^n text above, up to ~6.8; B x label ~7.1
ax_d = axes_in(LEFT + HALF + GAP, 4.35, HALF, 2.2)
LEGEND_Y = 3.35  # shared legend (2 rows) between the C/D x labels (~3.85) and panel E's title (~2.9)
ax_e = axes_in(LEFT, 0.55, WIDTH, 2.1)  # tall enough for the "% of mean amplitude" label

# breath shown in C and D: near the middle of the overview
i = int(np.argmin(np.abs(onsets / FS - P.overview_s / 2)))
o, nxt = onsets[i], onsets[i + 1]
lo, hi = o - ms_to_samples(100, FS), nxt + ms_to_samples(100, FS)
tb = (np.arange(lo, hi) - o) / FS * 1e3  # ms relative to onset
ms = lambda idx: (idx - o) / FS * 1e3  # sample index -> ms from onset
nxt_ms = ms(nxt)

# A: filtered EMG
show = t < P.overview_s
ax_a.plot(t[show], x[show, 0], color=C_EMG, lw=0.4)
h_zoom = ax_a.axvspan(lo / FS, hi / FS, color=mpu.COLORS["yellow"], alpha=0.45, label="Breath shown in C and D")
mpu.format_axis(ax_a, title="Filtered EMG$_{dia}$", ylabel="Amplitude", xlim=(0, P.overview_s), **TXT)
ax_a.tick_params(labelbottom=False)

# B: both envelopes normalized to their maximum in the 30 s segment, so their shapes and timing can be compared
tkeo_max, rms_max = tkeo_env.max(), rms_env.max()
ax_b.plot(t[show], rms_env[show] / rms_max, color=C_RMS, lw=1.0)
ax_b.plot(t[show], tkeo_env[show] / tkeo_max, color=C_TKEO, lw=1.2)
ax_b.axhline(t_on / tkeo_max, color=C_TH, ls="--", lw=0.9)
for on in onsets[onsets / FS < P.overview_s]:  # onsets only; offsets are shown on one breath in C and D
    ax_b.axvline(on / FS, color=C_ON, lw=0.9)
ax_b.axvspan(lo / FS, hi / FS, color=mpu.COLORS["yellow"], alpha=0.45)
mpu.format_axis(ax_b, title="", xlabel="Time [s]", ylabel="Normalized", xlim=(0, P.overview_s), **TXT)


def timing(ax, env, pk, off, color, label_level=True):
    """Peak, 70%-of-peak level, offset and T_I / T_E / T_TOT brackets for one breath."""
    ax.plot(ms(pk), env[pk], "o", color=C_TXT, ms=5)
    level = P.offset_fraction * env[pk]
    ax.plot([0, ms(off) + 80], [level] * 2, color=C_TXT, ls=":", lw=1.2)
    if label_level:
        ax.text(ms(off) + 80, level, f"{P.offset_fraction:.0%}", ha="right", va="bottom", fontsize=LEG - 1, color=C_TXT)
    ax.axvline(ms(off), color=color, ls=":", lw=1.6)
    ax.axvline(0, color=C_ON, lw=1.2)
    ax.axvline(nxt_ms, color=C_ON, lw=1.2)
    for x0, x1, y, txt in ((0, ms(off), 0.80, "$T_I$"), (ms(off), nxt_ms, 0.80, "$T_E$"), (0, nxt_ms, 0.93, "$T_{TOT}$")):
        ax.annotate("", xy=(x0, y), xytext=(x1, y), xycoords=("data", "axes fraction"),
                    arrowprops=dict(arrowstyle="<->", lw=0.9, color=C_TXT, shrinkA=0, shrinkB=0))
        ax.text((x0 + x1) / 2, y + 0.01, txt, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=LEG, color=C_TXT)


# C, D: the same breath on the same normalized scale as B (each envelope divided by its 30 s maximum)
tkeo_n, rms_n = tkeo_env / tkeo_max, rms_env / rms_max
y_top = max(tkeo_n[lo:hi].max(), rms_n[lo:hi].max()) / 0.72  # one y range for C and D; room for the brackets
y_bot = min(0.0, tkeo_n[lo:hi].min(), rms_n[lo:hi].min()) - 0.03 * y_top  # the lowpassed TKEO rings slightly below 0

# C: TKEO envelope of one breath (onset detection and 70% offset); green band = minimum duration above T_on
ax_c.plot(tb, tkeo_n[lo:hi], color=C_TKEO, lw=1.3)
ax_c.axhline(t_on / tkeo_max, color=C_TH, ls="--", lw=1.0)
ax_c.axvspan(0, P.min_duration_ms, color=C_ON, alpha=0.2)
timing(ax_c, tkeo_n, peaks[i], offsets[i], C_TKEO)
mpu.format_axis(ax_c, title="TKEO Timing", xlabel="Time from onset [ms]", ylabel="Normalized", xlim=(tb[0], tb[-1]), **TXT)

# D: moving RMS of the same breath; the same 70% rule on this envelope gives a different T_I
ax_d.plot(tb, rms_n[lo:hi], color=C_RMS, lw=1.8)
ax_d.axvspan(win_lo / FS * 1e3, win_hi / FS * 1e3, color=mpu.COLORS["light_blue"], alpha=0.3)  # 25-75 ms RMS window
timing(ax_d, rms_n, rms_peaks[i], rms_offsets[i], C_RMS, label_level=False)  # label would sit under RMS75
r75 = rms75[i] / rms_max
ax_d.plot(P.rms75_delay_ms, r75, "o", mfc=C_RMS, mec=C_TXT, ms=7, zorder=5)
ax_d.annotate("RMS$_{75}$", xy=(P.rms75_delay_ms, r75), xytext=(280, 0.22 * y_top), ha="left",  # in the empty dip after the burst
              fontsize=LEG, color=C_TXT, arrowprops=dict(arrowstyle="-", lw=0.8, color=C_TXT))
mpu.format_axis(ax_d, title="Moving RMS: RMS$_{75}$, Timing", xlabel="Time from onset [ms]", ylabel="Normalized", xlim=(tb[0], tb[-1]), **TXT)
for ax in (ax_b, ax_c, ax_d):  # one normalized y range for B, C and D
    ax.set_ylim(y_bot, y_top)

# one legend for the colour and line code shared by all panels
L = plt.Line2D
handles = [
    L([], [], color=C_EMG, lw=1.5, label="EMG$_{dia}$"),
    L([], [], color=C_TKEO, lw=2, label="TKEO envelope"),
    L([], [], color=C_RMS, lw=2, label=f"Moving RMS ({P.rms_window_ms:.0f} ms)"),
    h_zoom,
    L([], [], color=C_TH, ls="--", lw=1.2, label="$T_{on}$ (TKEO)"),
    L([], [], color=C_ON, lw=1.5, label="Onset"),
    L([], [], color=C_TXT, ls=":", lw=1.5, label="Offset (70% of peak)"),
    L([], [], color=C_TXT, marker="o", ls="none", ms=5, label="Burst peak"),
]
fig.legend(handles=handles, fontsize=LEG, frameon=False, ncol=4, loc="center",
           bbox_to_anchor=(0.5 * (2 * LEFT + WIDTH) / FIG_W, LEGEND_Y / FIG_H), columnspacing=1.0, handlelength=1.6)

# E: value 75 ms after each onset, from each envelope, as % of its own mean (the two envelopes have different units)
ax_e.axhline(100, color=C_EMG, lw=1.0)
ax_e.plot(onsets / FS, tkeo75 / tkeo75.mean() * 100, "s", mfc="none", mec=C_TKEO, mew=1.3, ms=5, label="TKEO envelope at 75 ms")
ax_e.plot(onsets / FS, rms75 / rms75.mean() * 100, "o", color=C_RMS, ms=4.5, label="RMS$_{75}$")
ax_e.axvspan(lo / FS, hi / FS, color=mpu.COLORS["yellow"], alpha=0.45)
mpu.format_axis(ax_e, title="Envelope Amplitude 75 ms After Onset, per Burst", xlabel="Time [s]", ylabel="% of mean amplitude", xlim=(0, P.duration_s), **TXT)
ax_e.legend(fontsize=LEG - 1, ncol=2, frameon=True, loc="upper left", handletextpad=0.3, columnspacing=1.0, borderpad=0.3)

for ax in (ax_a,):  # B-D are normalized and E in % of mean: plain numbers
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    ax.yaxis.get_offset_text().set_fontsize(TICK_SIZE)
# letters left of the y-axis label so they do not sit on the x10^n scale text (offset is a fraction of panel width)
fig.align_ylabels([ax_a, ax_b, ax_e])  # full-width panels: y labels in one column
for ax, label, xo in ((ax_a, "A", 0.09), (ax_b, "B", 0.09), (ax_c, "C", 0.24), (ax_d, "D", 0.24), (ax_e, "E", 0.09)):
    mpu.add_panel_label(ax, label, x_offset_factor=xo, y_offset_factor=0.01, fontsize=SUBTITLE_SIZE)

FIGURE_PATH = mpm.figure_dir().joinpath("figS_rms75.png")
mpu.save_figure(fig, FIGURE_PATH, dpi=600)
print(f"Figure saved to: {FIGURE_PATH}")
