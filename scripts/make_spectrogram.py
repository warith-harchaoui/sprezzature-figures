#!/usr/bin/env python3
"""Generate a publication-quality *spectrogram* figure as a standalone SVG.

A spectrogram is the heatmap of a short-time Fourier transform (STFT): the
signal is chopped into overlapping windows, each window is Fourier-transformed,
and the per-window power spectrum is stacked into a *time* (x) by *frequency*
(y) grid whose cell colour encodes *power* (loudness) in decibels. It is the
matplotlib ``specgram`` / ``librosa.display.specshow`` idiom — the canonical way
to *see* how the frequency content of a sound evolves over time.

This module builds the SVG string **by hand** (no matplotlib / seaborn /
plotly, no Vega): it synthesises a short, communicative audio clip with numpy —
a rising musical glissando riding over a steady bass drone, with three
percussive taps — computes a genuine Hann-windowed STFT (numpy ``rfft`` only),
maps power in dB onto a perceptually-uniform *viridis-like* ramp, and paints the
time-frequency grid as a mosaic of ``<rect>`` cells in the sprezzature-* house style:
Roboto type, ink ``#1D1D1F`` on white, rounded framing, a labelled colour
legend. The figure is a **static** poster-size raster — a spectrogram is a
time-frequency image whose x-axis already *is* time, so it gains nothing from
motion; the whole story is legible in one glance with no animation and no
JavaScript.

The example data is illustrative but physically real: the bright diagonal is the
glissando climbing through the audible band; the solid low band is the drone;
the three vertical streaks are the taps' broadband transients.

Usage
-----
    python make_spectrogram.py                 # writes the house SVG
    python make_spectrogram.py --out other.svg

Style rules: numpy docstrings, full typing, dict-as-record over ad-hoc classes,
generous comments.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations
from _render import svg_example_path, write_svg  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from _style import os_dark_style  # noqa: E402
from _svg import fmt_compact  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# Repo-relative default output — the one SVG artifact this figure ships.
_DEFAULT_OUT = (
    Path(__file__).resolve().parent.parent
    / "assets"
    / "svg-examples"
    / "spectrogram.svg"
)

# House-style tokens (mirrors the house-style constants, kept literal so this
# generator needs no import of the dataviz tier at build time).
_INK = "#1D1D1F"        # primary text
_SECONDARY = "#6E6E73"  # subtitle / secondary text
_BG = "#FFFFFF"         # white ground

# Sequential *power* ramp. A perceptually-uniform viridis-style stop list
# (dark blue → teal → green → yellow) reads loudness monotonically and is
# colour-vision-deficiency safe — it never leans on a red/green contrast.
# Anchor stops sampled from the canonical viridis colormap.
_VIRIDIS: Sequence[Tuple[float, str]] = (
    (0.00, "#440154"),
    (0.15, "#472D7B"),
    (0.30, "#3B528B"),
    (0.45, "#2C728E"),
    (0.60, "#21908C"),
    (0.72, "#27AD81"),
    (0.85, "#5DC863"),
    (0.93, "#AADC32"),
    (1.00, "#FDE725"),
)


# --------------------------------------------------------------------------- #
# Illustrative signal                                                          #
# --------------------------------------------------------------------------- #
#: Row records describing the three synthesised elements the spectrogram is
#: built to show: one ``"glissando"`` row (the rising-tone sweep), one or
#: more ``"drone"`` rows (a steady pitch plus its harmonic), and one row per
#: ``"tap"`` (a percussive broadband click at a given time). Genuinely
#: drives :func:`_synthesise_clip` — these rows *are* the clip's data, not a
#: per-sample dump (which would be 24,000 rows for no extra fidelity).
DEMO_DATA: List[Dict[str, Any]] = [
    {"component": "glissando", "start_hz": 200.0, "end_hz": 3200.0, "amplitude": 0.6},
    {"component": "drone", "hz": 120.0, "amplitude": 0.35},
    {"component": "drone", "hz": 240.0, "amplitude": 0.12},
    {"component": "tap", "time_s": 0.55},
    {"component": "tap", "time_s": 1.5},
    {"component": "tap", "time_s": 2.35},
]


def _synthesise_clip(
    components: Optional[List[Dict[str, Any]]] = None, seed: int = 3
) -> Tuple[np.ndarray, int]:
    """Synthesise a short, communicative mono audio clip from row records.

    The clip layers three easily-recognised elements so the spectrogram tells
    an obvious story:

    * a **glissando** — a sine whose frequency sweeps log-linearly upward,
      drawing the bright diagonal that climbs the frequency axis over time;
    * one or more steady **drones** at a fixed low pitch, the solid band(s)
      at the base;
    * percussive **taps** — short broadband clicks that paint vertical
      streaks spanning every frequency at a single instant.

    Parameters
    ----------
    components : list of dict or None
        Rows with a ``component`` key (``"glissando"``, ``"drone"`` or
        ``"tap"``) — see :data:`DEMO_DATA` for the field names each type
        takes. Defaults to :data:`DEMO_DATA`. Duration and sample rate are
        fixed (3 seconds at 8 kHz) so every clip stays comparable.
    seed : int, optional
        Seed for the additive noise floor and the taps' broadband bursts,
        for a reproducible figure.

    Returns
    -------
    tuple of (numpy.ndarray, int)
        ``(samples, sample_rate)`` — a 1-D float array in roughly ``[-1, 1]``
        and the sampling rate in hertz.
    """
    rows = list(components) if components else DEMO_DATA
    rng = np.random.default_rng(seed)
    sr = 8000                       # sample rate (Hz) — enough for a 0–4 kHz view
    dur = 3.0                       # clip length (seconds)
    t = np.linspace(0.0, dur, int(sr * dur), endpoint=False)

    gliss = np.zeros_like(t)
    drone = np.zeros_like(t)
    taps = np.zeros_like(t)

    for row in rows:
        kind = row.get("component")
        if kind == "glissando":
            f0 = float(row.get("start_hz", 200.0))
            f1 = float(row.get("end_hz", 3200.0))
            amp = float(row.get("amplitude", 0.6))
            # Instantaneous frequency sweeps log-linearly f0 -> f1; integrate
            # to get phase (cumulative), so the sweep is smooth.
            inst_f = f0 * (f1 / f0) ** (t / dur)
            phase = 2.0 * np.pi * np.cumsum(inst_f) / sr
            g = amp * np.sin(phase)
            # Fade in/out so it doesn't clip at the clip's edges.
            g *= np.clip(np.sin(np.pi * t / dur), 0.0, 1.0)
            gliss += g
        elif kind == "drone":
            hz = float(row.get("hz", 120.0))
            amp = float(row.get("amplitude", 0.35))
            drone += amp * np.sin(2.0 * np.pi * hz * t)
        elif kind == "tap":
            centre = float(row.get("time_s", 0.0))
            env = np.exp(-((t - centre) ** 2) / (2.0 * 0.004 ** 2))
            taps += env * rng.standard_normal(t.size)
    taps *= 0.5

    # A very quiet noise floor keeps the "silent" cells from being a dead flat
    # colour without letting the background speckle compete with the signal.
    floor = 0.003 * rng.standard_normal(t.size)

    signal = gliss + drone + taps + floor
    return signal.astype(np.float64), sr


# --------------------------------------------------------------------------- #
# Short-time Fourier transform (numpy rfft only)                              #
# --------------------------------------------------------------------------- #
def _stft_db(
    signal: np.ndarray,
    sr: int,
    *,
    n_fft: int = 320,
    hop: int = 64,
    f_max: float = 4000.0,
) -> Dict[str, np.ndarray]:
    """Compute a Hann-windowed STFT and return power in decibels.

    Parameters
    ----------
    signal : numpy.ndarray
        1-D real signal.
    sr : int
        Sample rate in hertz.
    n_fft : int, optional
        Window / transform length in samples (frequency resolution).
    hop : int, optional
        Hop between successive windows in samples (time resolution / overlap).
    f_max : float, optional
        Highest frequency (Hz) to keep in the returned grid.

    Returns
    -------
    dict of str to numpy.ndarray
        ``{"power_db": (n_freq, n_frames) array, "times": (n_frames,) seconds,
        "freqs": (n_freq,) hertz}``. ``power_db`` is normalised so its loudest
        cell is 0 dB and floored at a fixed dynamic range below that.
    """
    window = np.hanning(n_fft)
    # Frame the signal with the given hop; drop the trailing partial frame.
    n_frames = 1 + (signal.size - n_fft) // hop
    frames = np.stack(
        [signal[i * hop : i * hop + n_fft] * window for i in range(n_frames)],
        axis=1,
    )  # shape (n_fft, n_frames)

    spectrum = np.fft.rfft(frames, axis=0)          # (n_fft//2+1, n_frames)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)      # (n_fft//2+1,)
    times = (np.arange(n_frames) * hop + n_fft / 2) / sr

    # Keep only the sub-f_max band (the informative range for this clip).
    keep = freqs <= f_max
    power = power[keep]
    freqs = freqs[keep]

    # Convert to dB relative to the global peak, then floor the dynamic range.
    ref = power.max()
    power_db = 10.0 * np.log10(power / ref + 1e-12)
    dynamic_range = 55.0
    power_db = np.clip(power_db, -dynamic_range, 0.0)

    return {"power_db": power_db, "times": times, "freqs": freqs}


# --------------------------------------------------------------------------- #
# Colour ramp                                                                  #
# --------------------------------------------------------------------------- #
def _ramp_hex(t: float, stops: Sequence[Tuple[float, str]] = _VIRIDIS) -> str:
    """Sample a multi-stop sRGB colour ramp at position ``t`` in ``[0, 1]``.

    Parameters
    ----------
    t : float
        Position along the ramp, clamped to ``[0, 1]``.
    stops : sequence of (float, str)
        Ordered ``(position, "#RRGGBB")`` anchor stops.

    Returns
    -------
    str
        The interpolated colour as ``#RRGGBB``.
    """
    t = min(1.0, max(0.0, t))
    for (lo_t, lo_c), (hi_t, hi_c) in zip(stops, stops[1:]):
        if lo_t <= t <= hi_t:
            local = (t - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 0.0
            ar, ag, ab = int(lo_c[1:3], 16), int(lo_c[3:5], 16), int(lo_c[5:7], 16)
            br, bg, bb = int(hi_c[1:3], 16), int(hi_c[3:5], 16), int(hi_c[5:7], 16)
            r = round(ar + (br - ar) * local)
            g = round(ag + (bg - ag) * local)
            b = round(ab + (bb - ab) * local)
            return f"#{r:02X}{g:02X}{b:02X}"
    return stops[-1][1]


# --------------------------------------------------------------------------- #
# SVG assembly                                                                 #
# --------------------------------------------------------------------------- #


def build_svg(
    stft: Dict[str, np.ndarray],
    sr: int,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> str:
    """Assemble the full spectrogram SVG document as a string.

    Parameters
    ----------
    stft : dict of str to numpy.ndarray
        The output of :func:`_stft_db` — ``power_db``, ``times``, ``freqs``.
    sr : int
        Sample rate in hertz (used only for annotation).
    mode : str, optional
        Interactivity mode passed to :func:`_interactive.fullscreen_control`.
        One of ``"self-contained"`` (default, ships a hidden-until-live
        fullscreen button), ``"external"`` or ``"static"`` (no button).
    accessibility : str, optional
        Accepted for CLI parity but **not applied** — a documented no-op. Power
        (loudness) is encoded on the ``_VIRIDIS`` ramp, a *sequential,
        perceptually-uniform* colour map that is already colour-vision-deficiency
        and greyscale safe by construction (it never leans on a red/green
        contrast). Viridis is precisely tuned; re-spacing its anchors by
        lightness through a categorical accessibility level would de-tune the
        ramp and break its monotonic loudness read, so the level is intentionally
        not applied here.
    theme : str, optional
        Visual theme: ``"corporate"`` (default, Roboto -- byte-identical to
        the pre-theme render) or ``"academic"`` (LaTeX-style Latin Modern).
        See :func:`sprezzature_figures.fonts.chrome_stack_for_theme`.

    Returns
    -------
    str
        A complete, self-contained SVG document.
    """
    # ``accessibility`` is a deliberate no-op: viridis is a tuned sequential
    # perceptual map, already CVD/greyscale-safe (see the docstring). Reference
    # it so linters see the argument used.
    del accessibility
    font_family = chrome_stack_for_theme(theme)
    mono_family = mono_stack_for_theme(theme)
    power_db: np.ndarray = stft["power_db"]         # (n_freq, n_frames)
    times: np.ndarray = stft["times"]
    freqs: np.ndarray = stft["freqs"]
    n_freq, n_frames = power_db.shape

    # ---- canvas geometry -------------------------------------------------- #
    # Poster-size canvas: generous, readable at a glance, no cramping.
    width, height = 1240, 820
    m_left, m_right = 104, 156        # right margin holds the colour legend
    m_top, m_bottom = 132, 108
    plot_w = width - m_left - m_right
    plot_h = height - m_top - m_bottom

    t_lo, t_hi = float(times[0]), float(times[-1])
    f_lo, f_hi = float(freqs[0]), float(freqs[-1])

    def x_px(tsec: float) -> float:
        """Map a time (seconds) to a pixel column."""
        return m_left + (tsec - t_lo) / (t_hi - t_lo) * plot_w

    # Cell footprint. Cells tile the plot with no gaps; a hair of overlap
    # (+0.6px) hides seams that anti-aliasing would otherwise leave.
    cell_w = plot_w / n_frames
    cell_h = plot_h / n_freq

    # Normalise dB (already in [-range, 0]) to [0, 1] for the ramp.
    db_lo = float(power_db.min())
    db_hi = float(power_db.max())
    span = (db_hi - db_lo) or 1.0

    parts: List[str] = []

    # ---- header ----------------------------------------------------------- #
    title = "A rising tone climbs the frequency axis over three seconds"
    subtitle = (
        "Short-time Fourier transform of a synthesised clip — brighter = louder "
        ""
    )
    parts.append(
        f'<svg role="img" aria-label="{title}" '
        f'xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{font_family}">'
    )
    # OS-adaptive overrides (additive, media-gated so the default light render is
    # byte-for-byte unchanged). This is a PERCEPTUAL figure — loudness rides the
    # tuned, CVD-/greyscale-safe viridis ramp — so prefers-contrast must NOT
    # re-space the ramp; instead it STRENGTHENS the structure around the image:
    # the ink plot frame + axis ticks (stroke #1D1D1F) deepen to pure black and
    # the frame thickens, and the legend's hairline border (#D2D2D7) deepens to a
    # solid ink, so the chart reads harder-edged while every power cell keeps its
    # exact colour. Under forced-colors the same ink frame / ticks take CanvasText
    # so the axes survive Windows High Contrast (the viridis cells are left to the
    # browser — a sequential intensity map has no per-series encoding to protect).
    # Dark mode: flip the white paper + ink text to a dark surface, and re-light
    # the ink plot frame / axis ticks so they read on dark; the ramp is untouched.
    contrast_block = (
        "@media (prefers-contrast: more){\n"
        '  [stroke="#1D1D1F"]{stroke:#000000;}\n'
        '  rect[stroke="#1D1D1F"]{stroke-width:2.4;}\n'
        '  [stroke="#D2D2D7"]{stroke:#1D1D1F;stroke-width:1.6;}\n'
        "}"
    )
    forced_block = (
        "@media (forced-colors: active){\n"
        '  [stroke="#1D1D1F"]{stroke:CanvasText;}\n'
        '  [stroke="#D2D2D7"]{stroke:CanvasText;}\n'
        "}"
    )
    parts.append(
        "<style>"
        + contrast_block
        + forced_block
        + os_dark_style(extra='[stroke="#1D1D1F"]{stroke:#F2F2F7;}')
        + "</style>"
    )
    parts.append(
        f"<title>{title}</title>"
        f"<desc>Spectrogram: a time-by-frequency heatmap of a short-time Fourier "
        f"transform. A bright diagonal sweeps from low to high frequency (a rising "
        f"tone), a solid band at the base is a steady bass drone, and three vertical "
        f"streaks are percussive taps. Colour runs dark purple (quiet) to yellow "
        f"(loud).</desc>"
    )
    parts.append(f'<rect width="{width}" height="{height}" rx="18" fill="{_BG}"/>')
    parts.append(
        f'<text x="{m_left - 42}" y="58" font-size="29" font-weight="700" '
        f'fill="{_INK}">{title}</text>'
    )
    parts.append(
        f'<text x="{m_left - 42}" y="90" font-size="17" '
        f'fill="{_SECONDARY}">{subtitle}</text>'
    )

    # ---- heatmap cells (clipped to the plot rectangle) -------------------- #
    parts.append(
        f'<clipPath id="plot-clip"><rect x="{fmt_compact(m_left, decimals=2)}" y="{fmt_compact(m_top, decimals=2)}" '
        f'width="{fmt_compact(plot_w, decimals=2)}" height="{fmt_compact(plot_h, decimals=2)}" rx="6"/></clipPath>'
    )
    parts.append('<g clip-path="url(#plot-clip)" shape-rendering="crispEdges">')
    # Rounded frame ground behind the cells (shows through the clip corners).
    parts.append(
        f'<rect x="{fmt_compact(m_left, decimals=2)}" y="{fmt_compact(m_top, decimals=2)}" width="{fmt_compact(plot_w, decimals=2)}" '
        f'height="{fmt_compact(plot_h, decimals=2)}" fill="{_VIRIDIS[0][1]}"/>'
    )
    # Row j = 0 is the lowest frequency; draw it at the bottom of the plot.
    for j in range(n_freq):
        y = m_top + plot_h - (j + 1) * cell_h
        row = power_db[j]
        for i in range(n_frames):
            norm = (float(row[i]) - db_lo) / span
            colour = _ramp_hex(norm)
            x = m_left + i * cell_w
            parts.append(
                f'<rect x="{fmt_compact(x, decimals=2)}" y="{fmt_compact(y, decimals=2)}" '
                f'width="{fmt_compact(cell_w + 0.6, decimals=2)}" height="{fmt_compact(cell_h + 0.6, decimals=2)}" '
                f'fill="{colour}"/>'
            )
    parts.append("</g>")

    # ---- plot border ------------------------------------------------------ #
    parts.append(
        f'<rect x="{fmt_compact(m_left, decimals=2)}" y="{fmt_compact(m_top, decimals=2)}" width="{fmt_compact(plot_w, decimals=2)}" '
        f'height="{fmt_compact(plot_h, decimals=2)}" rx="6" fill="none" stroke="{_INK}" '
        f'stroke-width="1.4"/>'
    )

    # ---- x-axis (time) ---------------------------------------------------- #
    axis_y = m_top + plot_h
    for tsec in np.arange(0.0, t_hi + 1e-6, 0.5):
        if tsec < t_lo - 1e-6 or tsec > t_hi + 1e-6:
            continue
        gx = x_px(float(tsec))
        parts.append(
            f'<line x1="{fmt_compact(gx, decimals=2)}" y1="{fmt_compact(axis_y, decimals=2)}" x2="{fmt_compact(gx, decimals=2)}" '
            f'y2="{fmt_compact(axis_y + 7, decimals=2)}" stroke="{_INK}" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{fmt_compact(gx, decimals=2)}" y="{fmt_compact(axis_y + 28, decimals=2)}" text-anchor="middle" '
            f'font-size="15" font-family="{mono_family}" fill="{_SECONDARY}">'
            f"{tsec:.1f}</text>"
        )
    parts.append(
        f'<text x="{fmt_compact(m_left + plot_w / 2, decimals=2)}" y="{fmt_compact(axis_y + 62, decimals=2)}" '
        f'text-anchor="middle" font-size="17" fill="{_INK}">Time (seconds)</text>'
    )

    # ---- y-axis (frequency) ----------------------------------------------- #
    def y_px(fhz: float) -> float:
        """Map a frequency (Hz) to a pixel row (low freq at the bottom)."""
        return m_top + plot_h - (fhz - f_lo) / (f_hi - f_lo) * plot_h

    for fhz in (0, 1000, 2000, 3000, 4000):
        if fhz < f_lo - 1e-6 or fhz > f_hi + 1e-6:
            continue
        gy = y_px(float(fhz))
        parts.append(
            f'<line x1="{fmt_compact(m_left - 7, decimals=2)}" y1="{fmt_compact(gy, decimals=2)}" x2="{fmt_compact(m_left, decimals=2)}" '
            f'y2="{fmt_compact(gy, decimals=2)}" stroke="{_INK}" stroke-width="1.2"/>'
        )
        parts.append(
            f'<text x="{fmt_compact(m_left - 13, decimals=2)}" y="{fmt_compact(gy + 5, decimals=2)}" text-anchor="end" '
            f'font-size="15" font-family="{mono_family}" fill="{_SECONDARY}">'
            f"{fhz // 1000 if fhz else 0}{'k' if fhz else ''}</text>"
        )
    parts.append(
        f'<text x="30" y="{fmt_compact(m_top + plot_h / 2, decimals=2)}" text-anchor="middle" '
        f'font-size="17" fill="{_INK}" '
        f'transform="rotate(-90 30 {fmt_compact(m_top + plot_h / 2, decimals=2)})">Frequency (Hz)</text>'
    )

    # ---- annotations on the features ------------------------------------- #
    # Feature labels ride directly on the bright marks in white ink. On a
    # viridis field the loud cells are pale (green/yellow), so a soft dark
    # backing pill (not a hard stroke halo) keeps the words legible without
    # ringing the glyphs.
    def _labelled(cx: float, cy: float, text: str, *, anchor: str = "start") -> None:
        """Place a feature label over the heatmap with a soft backing pill."""
        pad_x, pad_y = 8.0, 6.0
        char_w = 8.6                       # rough advance for 15px Roboto 600
        w = len(text) * char_w + 2 * pad_x
        h = 24.0
        if anchor == "start":
            rx = cx - pad_x
        elif anchor == "end":
            rx = cx - (w - pad_x)
        else:  # middle
            rx = cx - w / 2
        parts.append(
            f'<rect x="{fmt_compact(rx, decimals=2)}" y="{fmt_compact(cy - h + pad_y, decimals=2)}" width="{fmt_compact(w, decimals=2)}" '
            f'height="{fmt_compact(h, decimals=2)}" rx="7" fill="#1D1D1F" fill-opacity="0.42"/>'
        )
        parts.append(
            f'<text x="{fmt_compact(cx, decimals=2)}" y="{fmt_compact(cy, decimals=2)}" text-anchor="{anchor}" '
            f'font-size="15" font-weight="600" fill="#FFFFFF">{text}</text>'
        )

    # Label the glissando diagonal.
    _labelled(x_px(2.28), y_px(2650.0), "rising tone", anchor="start")
    # Label the drone band.
    _labelled(x_px(0.14), y_px(560.0), "bass drone", anchor="start")
    # Label one of the percussive taps (the broadband vertical streaks).
    _labelled(x_px(1.5), y_px(3750.0), "percussive tap", anchor="middle")

    # ---- colour legend (vertical power ramp) ------------------------------ #
    leg_x = width - m_right + 44
    leg_w = 20
    leg_top = m_top + 10
    leg_h = plot_h - 20
    grad_id = "power-ramp"
    parts.append(f'<defs><linearGradient id="{grad_id}" x1="0" y1="1" x2="0" y2="0">')
    for pos, col in _VIRIDIS:
        parts.append(f'<stop offset="{fmt_compact(pos * 100, decimals=2)}%" stop-color="{col}"/>')
    parts.append("</linearGradient></defs>")
    # No dark ring around the swatch — a hairline light-neutral border keeps
    # the ramp crisp on white without a hard black outline.
    parts.append(
        f'<rect x="{fmt_compact(leg_x, decimals=2)}" y="{fmt_compact(leg_top, decimals=2)}" width="{leg_w}" '
        f'height="{fmt_compact(leg_h, decimals=2)}" rx="5" fill="url(#{grad_id})" '
        f'stroke="#D2D2D7" stroke-width="1"/>'
    )
    # Legend tick labels: 0 dB (loud) at the top, floor at the bottom.
    for frac, lbl in ((1.0, "0"), (0.5, f"{int(db_lo / 2)}"), (0.0, f"{int(db_lo)}")):
        ly = leg_top + (1.0 - frac) * leg_h
        parts.append(
            f'<text x="{fmt_compact(leg_x + leg_w + 9, decimals=2)}" y="{fmt_compact(ly + 5, decimals=2)}" '
            f'font-size="14" font-family="{mono_family}" fill="{_SECONDARY}">{lbl}</text>'
        )
    parts.append(
        f'<text x="{fmt_compact(leg_x + leg_w / 2, decimals=2)}" y="{fmt_compact(leg_top - 14, decimals=2)}" '
        f'text-anchor="middle" font-size="15" fill="{_INK}">Power</text>'
    )
    parts.append(
        f'<text x="{fmt_compact(leg_x + leg_w / 2, decimals=2)}" y="{fmt_compact(leg_top + leg_h + 24, decimals=2)}" '
        f'text-anchor="middle" font-size="13" fill="{_SECONDARY}">dB</text>'
    )

    parts.append(fullscreen_control(width, height, mode))
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser for the script."""
    parser = argparse.ArgumentParser(
        prog="make_spectrogram",
        description="Write the house-style spectrogram (STFT heatmap) SVG example.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Destination SVG path (default: the shipped example).",
    )
    parser.add_argument(
        "--seed", type=int, default=3, help="Random seed for the synthesised clip."
    )
    parser.add_argument(
        "--mode",
        choices=("self-contained", "external", "static"),
        default="self-contained",
        help="Interactivity mode for the fullscreen control (default: self-contained).",
    )
    parser.add_argument(
        "--accessibility",
        choices=(
            "universal", "high-contrast", "monochrome",
            "deuteranopia", "protanopia", "tritanopia",
        ),
        default="universal",
        help=(
            "palette accessibility level (accepted for CLI parity but a no-op "
            "here: the viridis power ramp is a tuned sequential perceptual map, "
            "already CVD- and greyscale-safe, so a categorical level is not applied)"
        ),
    )
    parser.add_argument(
        "--theme",
        choices=("corporate", "academic"),
        default="corporate",
        help="visual theme: corporate (default, Roboto) or academic (LaTeX-style Latin Modern)",
    )
    return parser


def make_spectrogram(
    data: Optional[List[Dict[str, Any]]] = None,
    *,
    out: Optional[Path | str] = None,
    title: str = "",
    seed: int = 3,
    mode: str = "self-contained",
    accessibility: str = "universal",
    theme: str = "corporate",
) -> Path:
    """Synthesise the clip, compute its STFT, and write the spectrogram SVG.

    Parameters
    ----------
    data : list[dict[str, Any]] or None
        Rows describing the clip's glissando/drone/tap components (see
        :data:`DEMO_DATA`). Defaults to :data:`DEMO_DATA`.
    out : Path, str, or None
        Output path (.svg). Defaults to
        ``assets/svg-examples/spectrogram.svg``.
    title : str, optional
        Accepted for dispatcher parity; the figure's own headline states the
        specific takeaway, so this is unused.
    seed : int, optional
        Seed for the reproducible noise floor and tap bursts.
    mode, accessibility : str
        Forwarded to :func:`build_svg`.
    theme : str, optional
        Visual theme. Forwarded to :func:`build_svg`.

    Returns
    -------
    Path
        Absolute path to the written SVG file.
    """
    del title
    signal, sr = _synthesise_clip(data, seed=seed)
    stft = _stft_db(signal, sr)
    svg = build_svg(stft, sr, mode, accessibility=accessibility, theme=theme)
    dest = Path(out) if out else svg_example_path(__file__, "spectrogram")
    return write_svg(dest, svg, theme=theme)


def main(argv: List[str] | None = None) -> int:
    """CLI entry point: synthesise the clip, compute its STFT, write the SVG."""
    args = _build_parser().parse_args(argv)
    signal, sr = _synthesise_clip(seed=args.seed)
    stft = _stft_db(signal, sr)
    svg = build_svg(stft, sr, args.mode, accessibility=args.accessibility, theme=args.theme)
    write_svg(args.out, svg, theme=args.theme)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
