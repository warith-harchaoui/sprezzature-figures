#!/usr/bin/env python3
"""
explain_model
=============

Model-explainability dispatcher. Given a fitted model and a dataset,
picks the right engine and emits summary + local explanations in the
sprezzature-* house style.

Engines
-------

======================  ==========================================================
``shap`` (default)      Tree, linear, kernel — universal fallback via
                        :class:`shap.Explainer`.
``shapash``             Full HTML report for a business stakeholder — wraps
                        SHAP under the hood.
``timeshap``            Recurrent / attention-based time-series predictors
                        (LSTM, GRU, transformer classifier on sequences).
``lime``                Deep black-box classifiers where KernelSHAP is
                        impractical; local linear approximation only.
======================  ==========================================================

Dispatch (when ``--engine auto``):

    tree model (XGBoost / LightGBM / RandomForest / sklearn.tree)
        → SHAP TreeExplainer
    linear / logistic
        → SHAP LinearExplainer
    torch.nn.Module + 3-D input
        → TimeSHAP
    otherwise
        → SHAP Explainer (falls back to KernelSHAP)

Pass ``--report shapash`` at any time to add the Shapash HTML report on
top of whichever engine ran.

Usage
-----
::

    # Auto-dispatch (default) on a scikit-learn model
    python explain_model.py --model model.pkl --data X.csv --out ./explain/

    # Business-facing report
    python explain_model.py --model model.pkl --data X.csv \\
        --engine shapash --report shapash --out ./explain/

    # LSTM time-series classifier
    python explain_model.py --model seq_model.pkl --data X.npy \\
        --engine timeshap --sequence-cols "t_0,t_1,t_2,t_3,t_4" \\
        --out ./explain/

Notes
-----
* Python 3.10+, ``pip install -r requirements-explain.txt``.
* Deferred imports throughout: importing this module does not pull
  shap / shapash / timeshap / lime unless the corresponding path is
  taken.

Author
------
`Warith Harchaoui, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _argparse import make_parser  # noqa: E402
from _interactive import fullscreen_control  # noqa: E402
from _render import write_svg  # noqa: E402
from _style import BG, GRIDLINE, INK, SECONDARY, diverging_pair, load_palette, os_dark_style  # noqa: E402
from _svg import color_ramp, foreground_tip_css, fmt_number, svg_open, tooltip_bubble, xml_escape  # noqa: E402
import make_bar  # noqa: E402
import make_waterfall  # noqa: E402
from sprezzature_figures.fonts import chrome_stack_for_theme, mono_stack_for_theme  # noqa: E402


# ------------------------------------------------------------------
# Model / data loading
# ------------------------------------------------------------------
def load_model(path: str) -> Any:
    """Load a pickled model.

    .. warning::
        Unpickling executes arbitrary code. Only load a model file **you
        produced or trust** — never a pickle from an untrusted source.

    Parameters
    ----------
    path : str
        Filesystem path to a pickle. ``joblib`` is used when the file
        extension is ``.joblib``.

    Returns
    -------
    object
        The unpickled model.
    """
    p = Path(path)
    if p.suffix.lower() == ".joblib":
        import joblib
        return joblib.load(p)
    with p.open("rb") as fh:
        return pickle.load(fh)


def load_data(path: str) -> Any:
    """Load a data matrix.

    Parameters
    ----------
    path : str
        Path to CSV / JSON / Parquet / NPY.

    Returns
    -------
    pandas.DataFrame or numpy.ndarray
        A DataFrame for tabular inputs; a numpy array for NPY (needed
        for the TimeSHAP path).
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".csv":
        import pandas as pd
        return pd.read_csv(p)
    if ext == ".json":
        import pandas as pd
        return pd.read_json(p)
    if ext in {".parquet", ".pq"}:
        import pandas as pd
        return pd.read_parquet(p)
    if ext == ".npy":
        import numpy as np
        return np.load(p)
    raise SystemExit(f"Unsupported data extension: {ext}")


# ------------------------------------------------------------------
# Engine dispatch
# ------------------------------------------------------------------
def pick_engine(model: Any, data: Any) -> str:
    """Auto-dispatch to SHAP or TimeSHAP from model + data shape.

    Parameters
    ----------
    model : object
        The fitted model.
    data : pandas.DataFrame or numpy.ndarray
        Feature matrix or sequence tensor.

    Returns
    -------
    str
        ``"timeshap"`` for a 3-D torch sequence model, otherwise ``"shap"``.
        ``"lime"`` and ``"shapash"`` are never auto-selected — they are only
        used when the user passes ``--engine`` explicitly (LIME as a black-box
        fallback; Shapash for its HTML report).
    """
    module = getattr(type(model), "__module__", "") or ""
    lower = module.lower()

    if "torch" in lower and hasattr(data, "ndim") and getattr(data, "ndim", 0) == 3:
        return "timeshap"
    if any(key in lower for key in ("xgboost", "lightgbm", "catboost", "sklearn.ensemble", "sklearn.tree")):
        return "shap"
    if any(key in lower for key in ("sklearn.linear_model", "linear")):
        return "shap"
    return "shap"


# ------------------------------------------------------------------
# Hand-authored SVG rendering
#
# No matplotlib, no Vega, no plotly, no seaborn anywhere in this module
# (see references/figure-catalog.md for the house policy). The summary
# bar and the per-row waterfall reuse the catalogue's own generators
# (``make_bar.py``, ``make_waterfall.py``) since their data shape is a
# genuine fit; the beeswarm and dependence scatter are bespoke, built
# from the same shared ``_svg`` / ``_style`` primitives every catalogue
# generator uses, because SHAP's beeswarm (one swarm row per feature,
# continuous colour by raw feature value) and its dependence scatter
# (arbitrary x/y roles) do not fit either catalogue generator's fixed
# data contract (``make_beeswarm.py`` swarms one shared axis across a
# small set of categorical groups; ``make_scatter.py``'s roles are
# hard-coded to its own demo, not generic x/y).
# ------------------------------------------------------------------
def _top_features_by_mean_abs_shap(shap_values: Any, top_n: int) -> List[int]:
    """Indices of the `top_n` features by mean |SHAP value|, descending."""
    import numpy as np
    mean_abs = np.abs(shap_values.values).mean(axis=0)
    return [int(i) for i in np.argsort(-mean_abs)[:top_n]]


def _write_shap_bar_svg(
    shap_values: Any, feat_names: List[str], top_idx: List[int], out: Path,
) -> Path:
    """Mean |SHAP value| per feature, reusing the house bar-chart generator."""
    import numpy as np
    mean_abs = np.abs(shap_values.values).mean(axis=0)
    rows = [{"region": feat_names[i], "value": float(mean_abs[i])} for i in top_idx]
    return make_bar.make_bar(
        rows, out=out,
        title="Mean |SHAP value| by feature",
        subtitle=f"Top {len(rows)} features ranked by mean absolute impact on the prediction",
        x_label="Feature", y_label="Mean |SHAP value|",
    )


def _write_shap_beeswarm_svg(
    shap_values: Any, feat_names: List[str], top_idx: List[int], out: Path,
) -> Path:
    """Per-feature SHAP-value swarm, coloured by each point's raw feature value.

    One horizontal swarm band per feature (ranked by importance, most
    important at the top), points positioned by SHAP value and coloured
    on a blue -> red ramp by the feature's own raw value at that row,
    the standard SHAP beeswarm reading. Reuses
    :func:`make_beeswarm._swarm_positions` (the collision-avoidance
    layout every catalogue swarm plot already runs) for the vertical
    jitter within each band.
    """
    import numpy as np
    from make_beeswarm import _swarm_positions  # shared collision-avoidance layout

    low_hex, high_hex = diverging_pair(cvd_safe=True)
    ramp_stops = [(0.0, low_hex), (1.0, high_hex)]

    n_features = len(top_idx)
    n_points = shap_values.values.shape[0]
    width, row_h = 820, 34
    plot_x, plot_y = 190.0, 70.0
    right_margin, bottom_reserved = 40.0, 60.0
    plot_w = width - plot_x - right_margin
    height = int(plot_y + n_features * row_h + bottom_reserved)
    radius = 3.2

    all_vals = shap_values.values[:, top_idx]
    v_max = float(np.abs(all_vals).max()) or 1.0

    def x_for(v: float) -> float:
        return plot_x + (v + v_max) / (2 * v_max) * plot_w

    chrome_family = chrome_stack_for_theme("corporate")
    mono_family = mono_stack_for_theme("corporate")
    parts: List[str] = []
    parts.append(svg_open(width, height, "shap-bee-title", "shap-bee-desc", font_family=chrome_family))
    parts.append('<title id="shap-bee-title">SHAP value distribution by feature</title>')
    parts.append(
        f'<desc id="shap-bee-desc">Beeswarm of SHAP values for the top {n_features} features, '
        'one row per feature ranked by importance, coloured by each point’s raw feature value.</desc>'
    )
    total_dots = n_features * n_points
    parts.append(
        "<style>"
        ".dot{transition:r .12s ease;}"
        ".dot:hover,.dot:focus{r:5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.dot{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(total_dots, mark_prefix="shapdot-hit", tip_prefix="shapdot-tip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + os_dark_style()
        + "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')

    axis_bottom = plot_y + n_features * row_h
    zero_x = x_for(0.0)
    parts.append(
        f'<line x1="{zero_x:.1f}" y1="{plot_y:.1f}" x2="{zero_x:.1f}" y2="{axis_bottom:.1f}" '
        f'stroke="{INK}" stroke-width="1" opacity="0.35"/>'
    )

    tips: List[str] = []
    tip_i = 0
    for row_i, feat_idx in enumerate(top_idx):
        cy = plot_y + row_i * row_h + row_h / 2.0
        parts.append(
            f'<text x="{plot_x - 12:.1f}" y="{cy + 4:.1f}" font-size="12" fill="{INK}" '
            f'text-anchor="end">{xml_escape(str(feat_names[feat_idx]))}</text>'
        )
        vals = shap_values.values[:, feat_idx]
        raw = shap_values.data[:, feat_idx] if hasattr(shap_values, "data") else vals
        raw_min, raw_max = float(np.min(raw)), float(np.max(raw))
        raw_span = (raw_max - raw_min) or 1.0
        order = list(np.argsort(vals))
        items = [(x_for(float(vals[j])), 0.0) for j in order]
        ys = _swarm_positions(items, cy, radius)
        for (x, _), y, j in zip(items, ys, order):
            t = (float(raw[j]) - raw_min) / raw_span
            color = color_ramp(t, ramp_stops)
            tip = f"{feat_names[feat_idx]}: SHAP {float(vals[j]):+.3f}, feature value {float(raw[j]):.3g}"
            parts.append(
                f'<circle id="shapdot-hit-{tip_i}" class="dot hit" tabindex="0" cx="{x:.1f}" cy="{y:.1f}" '
                f'r="{radius:.1f}" fill="{color}" stroke="{BG}" stroke-width="0.6">'
                f'<title>{xml_escape(tip)}</title></circle>'
            )
            tips.append(
                tooltip_bubble(
                    x, y - radius - 6, [tip],
                    canvas_w=width, canvas_h=height, ink=INK, secondary=SECONDARY, border=GRIDLINE,
                    elem_id=f"shapdot-tip-{tip_i}",
                )
            )
            tip_i += 1
    parts.extend(tips)

    parts.append(
        f'<line x1="{plot_x:.1f}" y1="{axis_bottom:.1f}" x2="{plot_x + plot_w:.1f}" y2="{axis_bottom:.1f}" '
        f'stroke="{INK}" stroke-width="1.2"/>'
    )
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = -v_max + frac * 2 * v_max
        tx = x_for(v)
        parts.append(
            f'<text x="{tx:.1f}" y="{axis_bottom + 18:.1f}" font-size="10.5" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{fmt_number(v)}</text>'
        )
    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{axis_bottom + 38:.1f}" font-size="12" fill="{INK}" '
        'text-anchor="middle">SHAP value (impact on model output)</text>'
    )

    leg_x, leg_y, leg_w = plot_x, 30.0, 140.0
    for i in range(20):
        t0, t1 = i / 20.0, (i + 1) / 20.0
        parts.append(
            f'<rect x="{leg_x + t0 * leg_w:.1f}" y="{leg_y:.1f}" width="{leg_w / 20.0 + 0.5:.1f}" '
            f'height="8" fill="{color_ramp((t0 + t1) / 2, ramp_stops)}"/>'
        )
    parts.append(f'<text x="{leg_x:.1f}" y="{leg_y - 6:.1f}" font-size="10.5" fill="{SECONDARY}">Feature value: low</text>')
    parts.append(
        f'<text x="{leg_x + leg_w:.1f}" y="{leg_y - 6:.1f}" font-size="10.5" fill="{SECONDARY}" '
        'text-anchor="end">high</text>'
    )

    parts.append(fullscreen_control(width, height))
    parts.append("</svg>")
    return write_svg(out, "\n".join(parts), theme="corporate")


def _write_shap_dependence_svg(
    shap_values: Any, feat_names: List[str], feat_idx: int, out: Path,
) -> Path:
    """Feature value vs. its own SHAP value, one dot per explained row."""
    import numpy as np

    xs = shap_values.data[:, feat_idx] if hasattr(shap_values, "data") else shap_values.values[:, feat_idx]
    ys = shap_values.values[:, feat_idx]
    feat_name = str(feat_names[feat_idx])

    width, height = 620, 420
    plot_x, plot_y = 64.0, 70.0
    right_margin, bottom_reserved = 30.0, 60.0
    plot_w = width - plot_x - right_margin
    plot_h = height - plot_y - bottom_reserved

    x_min, x_max = float(np.min(xs)), float(np.max(xs))
    y_min, y_max = float(np.min(ys)), float(np.max(ys))
    x_pad = (x_max - x_min) * 0.08 or 1.0
    y_pad = (y_max - y_min) * 0.10 or 1.0
    x0, x1 = x_min - x_pad, x_max + x_pad
    y0, y1 = y_min - y_pad, y_max + y_pad

    def px(v: float) -> float:
        return plot_x + (v - x0) / (x1 - x0) * plot_w

    def py(v: float) -> float:
        return plot_y + plot_h - (v - y0) / (y1 - y0) * plot_h

    blue = load_palette().get("Blue", "#007AFF")
    chrome_family = chrome_stack_for_theme("corporate")
    mono_family = mono_stack_for_theme("corporate")
    title = f"SHAP dependence: {feat_name}"

    parts: List[str] = []
    parts.append(svg_open(width, height, "shap-dep-title", "shap-dep-desc", font_family=chrome_family))
    parts.append(f'<title id="shap-dep-title">{xml_escape(title)}</title>')
    parts.append(
        f'<desc id="shap-dep-desc">SHAP value versus raw value of {xml_escape(feat_name)}, '
        'one point per explained row.</desc>'
    )
    parts.append(
        "<style>"
        ".dot{transition:r .12s ease;}"
        ".dot:hover,.dot:focus{r:5.5;outline:none;}"
        "@media (prefers-reduced-motion: reduce){.dot{transition:none;}}"
        ".tip{opacity:0;pointer-events:none;transition:opacity .12s ease}"
        + foreground_tip_css(len(xs), mark_prefix="dep-hit", tip_prefix="dep-tip")
        + "@media (prefers-reduced-motion:reduce){.tip{transition:none}}"
        + os_dark_style()
        + "</style>"
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="{BG}"/>')
    parts.append(f'<text x="{plot_x:.1f}" y="34" font-size="18" font-weight="700" fill="{INK}">{xml_escape(title)}</text>')

    if y0 < 0 < y1:
        zy = py(0.0)
        parts.append(
            f'<line x1="{plot_x:.1f}" y1="{zy:.1f}" x2="{plot_x + plot_w:.1f}" y2="{zy:.1f}" '
            f'stroke="{INK}" stroke-width="1" opacity="0.35"/>'
        )

    for i in range(6):
        xv = x0 + i / 5.0 * (x1 - x0)
        tx = px(xv)
        parts.append(
            f'<line x1="{tx:.1f}" y1="{plot_y:.1f}" x2="{tx:.1f}" y2="{plot_y + plot_h:.1f}" '
            f'stroke="{GRIDLINE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{tx:.1f}" y="{plot_y + plot_h + 18:.1f}" font-size="10.5" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="middle">{fmt_number(xv)}</text>'
        )
    for i in range(5):
        yv = y0 + i / 4.0 * (y1 - y0)
        ty = py(yv)
        parts.append(
            f'<text x="{plot_x - 8:.1f}" y="{ty + 4:.1f}" font-size="10.5" font-family="{mono_family}" '
            f'fill="{SECONDARY}" text-anchor="end">{fmt_number(yv)}</text>'
        )

    parts.append(
        f'<text x="{plot_x + plot_w / 2:.1f}" y="{height - 12:.1f}" font-size="12" fill="{INK}" '
        f'text-anchor="middle">{xml_escape(feat_name)} (raw value)</text>'
    )
    parts.append(
        f'<text x="16" y="{plot_y + plot_h / 2:.1f}" font-size="12" fill="{INK}" text-anchor="middle" '
        f'transform="rotate(-90 16 {plot_y + plot_h / 2:.1f})">SHAP value</text>'
    )

    tips: List[str] = []
    for i in range(len(xs)):
        x, y = px(float(xs[i])), py(float(ys[i]))
        tip = f"{feat_name} = {float(xs[i]):.3g}, SHAP {float(ys[i]):+.3f}"
        parts.append(
            f'<circle id="dep-hit-{i}" class="dot hit" tabindex="0" cx="{x:.1f}" cy="{y:.1f}" r="3.5" '
            f'fill="{blue}" opacity="0.75"><title>{xml_escape(tip)}</title></circle>'
        )
        tips.append(
            tooltip_bubble(
                x, y - 12, [tip], canvas_w=width, canvas_h=height,
                ink=INK, secondary=SECONDARY, border=GRIDLINE, elem_id=f"dep-tip-{i}",
            )
        )
    parts.extend(tips)

    parts.append(fullscreen_control(width, height))
    parts.append("</svg>")
    return write_svg(out, "\n".join(parts), theme="corporate")


def _write_shap_waterfall_svg(shap_values: Any, row_idx: int, feat_names: List[str], out: Path) -> Path:
    """Per-row SHAP contribution breakdown, reusing the house waterfall generator."""
    row = shap_values[row_idx]
    base_values = row.base_values
    base = float(base_values[0]) if hasattr(base_values, "__len__") else float(base_values)
    contributions = row.values
    order = sorted(range(len(contributions)), key=lambda i: -abs(float(contributions[i])))

    rows: List[Dict[str, Any]] = [{"label": "Base value", "value": base, "kind": "total"}]
    running = base
    for i in order:
        val = float(contributions[i])
        rows.append({"label": str(feat_names[i]), "value": val, "kind": "positive" if val >= 0 else "negative"})
        running += val
    rows.append({"label": "Prediction", "value": running, "kind": "total"})

    return make_waterfall.make_waterfall(
        rows, out=out,
        title=f"SHAP contribution breakdown, row {row_idx}",
        subtitle="From the base value to this row's prediction",
    )


def _write_static_explanation_report(out: Path, title: str, sections: List[Any]) -> Path:
    """Assemble a static HTML report embedding hand-authored SVG figures.

    A simplified, static equivalent of Shapash's own multi-tab plotly
    dashboard, not a feature-for-feature clone: one page, one figure per
    section, no client-side interactivity beyond each SVG's own native
    CSS hover tooltips.
    """
    figures = []
    for heading, svg_path in sections:
        svg_text = svg_path.read_text(encoding="utf-8")
        figures.append(f"<section><h2>{xml_escape(heading)}</h2><figure>{svg_text}</figure></section>")
    body = "\n".join(figures)
    html = (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<title>{xml_escape(title)}</title>"
        "<style>body{font-family:Roboto,system-ui,sans-serif;max-width:900px;"
        "margin:2rem auto;padding:0 1rem;background:#FFFFFF;color:#1D1D1F;} "
        "h1{font-size:24px;} h2{font-size:16px;color:#6E6E73;margin-top:2.5rem;} "
        "figure{margin:0;} svg{max-width:100%;height:auto;}"
        "@media (prefers-color-scheme: dark){body{background:#1D1D1F;color:#F5F5F7;}}"
        "</style>"
        f"</head><body><h1>{xml_escape(title)}</h1>{body}</body></html>"
    )
    out.write_text(html, encoding="utf-8")
    return out


# ------------------------------------------------------------------
# SHAP path
# ------------------------------------------------------------------
def run_shap(model: Any, data: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Compute SHAP explanations and write hand-authored SVG plots to ``ctx['out']``.

    Parameters
    ----------
    model : object
        Fitted estimator.
    data : pandas.DataFrame
        Feature matrix.
    ctx : dict
        Context bag with keys ``out`` (Path), ``n_background`` (int),
        ``n_explain`` (int), ``top_n`` (int), ``dark`` (bool),
        ``waterfall_row`` (int or None), ``link`` (str).

    Returns
    -------
    dict
        Summary metadata (feature ranks, files written).
    """
    import numpy as np
    import shap

    out: Path = ctx["out"]
    out.mkdir(parents=True, exist_ok=True)

    n_background = min(ctx.get("n_background", 100), len(data))
    n_explain = min(ctx.get("n_explain", 500), len(data))
    background = data.sample(n_background, random_state=42) if hasattr(data, "sample") else data[:n_background]
    explain_rows = data.sample(n_explain, random_state=7) if hasattr(data, "sample") else data[:n_explain]

    explainer = shap.Explainer(model, background)
    shap_values = explainer(explain_rows)
    feat_names = list(explain_rows.columns) if hasattr(explain_rows, "columns") else [f"f{i}" for i in range(explain_rows.shape[1])]

    bar_top_idx = _top_features_by_mean_abs_shap(shap_values, ctx.get("top_n", 20))
    _write_shap_bar_svg(shap_values, feat_names, bar_top_idx, out / "summary_bar.svg")
    _write_shap_beeswarm_svg(shap_values, feat_names, bar_top_idx, out / "summary_beeswarm.svg")

    # dependence plots for top-N features by mean |shap| (a smaller default
    # than the bar/beeswarm's top_n, matching this tool's pre-SVG behavior)
    dep_top_idx = _top_features_by_mean_abs_shap(shap_values, ctx.get("top_n", 5))
    for i in dep_top_idx:
        try:
            _write_shap_dependence_svg(shap_values, feat_names, i, out / f"dependence_{feat_names[i]}.svg")
        except Exception as exc:  # noqa: BLE001 — plot best-effort
            print(f"[warn] dependence plot for {feat_names[i]} failed: {exc}", file=sys.stderr)

    # waterfall for the row with largest absolute prediction
    row_idx = ctx.get("waterfall_row")
    if row_idx is None:
        try:
            preds = model.predict(explain_rows) if hasattr(model, "predict") else np.abs(shap_values.values).sum(axis=1)
            row_idx = int(np.argmax(np.abs(preds)))
        except Exception:  # noqa: BLE001
            row_idx = 0
    try:
        _write_shap_waterfall_svg(shap_values, row_idx, feat_names, out / f"waterfall_row_{row_idx}.svg")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] waterfall failed: {exc}", file=sys.stderr)

    # Persist shap values
    try:
        import pandas as pd
        vals_df = pd.DataFrame(shap_values.values, columns=feat_names)
        vals_df.to_parquet(out / "shap_values.parquet")
    except Exception as exc:  # noqa: BLE001 — parquet needs pyarrow; optional artifact
        # Unlike the plots, surface a note so the missing artifact isn't silent
        # (matches the sibling plot handlers' [warn] convention).
        print(f"[warn] could not write shap_values.parquet ({exc}); skipping.",
              file=sys.stderr)

    return {
        "engine": "shap",
        "n_background": n_background,
        "n_explain": n_explain,
        "top_features": [feat_names[i] for i in bar_top_idx],
        "waterfall_row": int(row_idx),
        "files": [p.name for p in sorted(out.glob("*"))],
    }


# ------------------------------------------------------------------
# Shapash path
# ------------------------------------------------------------------
def run_shapash(model: Any, data: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Compute contributions via Shapash, render a static hand-authored-SVG report.

    Shapash's own ``generate_report()`` is a plotly-backed multi-tab
    dashboard; it is never called. ``SmartExplainer`` still does real
    work here: its ``compile()`` step runs Shapash's own consistency
    checks against the SHAP contributions this function computes, and
    the compiled object is saved for whatever downstream Shapash tooling
    the caller reaches for beyond this report. The report itself is a
    single static HTML page assembling this module's own SVG plots, a
    simplified equivalent of Shapash's dashboard, not a feature-for-
    feature clone (see :func:`_write_static_explanation_report`).
    """
    import numpy as np
    import pandas as pd
    import shap
    from shapash import SmartExplainer

    out: Path = ctx["out"]
    out.mkdir(parents=True, exist_ok=True)

    n_background = min(ctx.get("n_background", 100), len(data))
    n_explain = min(ctx.get("n_explain", 500), len(data))
    background = data.sample(n_background, random_state=42) if hasattr(data, "sample") else data[:n_background]
    explain_rows = data.sample(n_explain, random_state=7) if hasattr(data, "sample") else data[:n_explain]

    explainer = shap.Explainer(model, background)
    shap_values = explainer(explain_rows)
    feat_names = list(explain_rows.columns) if hasattr(explain_rows, "columns") else [f"f{i}" for i in range(explain_rows.shape[1])]

    contributions = pd.DataFrame(shap_values.values, columns=feat_names, index=getattr(explain_rows, "index", None))
    xpl = SmartExplainer(model=model)
    y_pred = None
    if hasattr(model, "predict"):
        try:
            y_pred = model.predict(explain_rows)
        except Exception:  # noqa: BLE001 — predictions are an optional overlay; compile below still works with y_pred=None
            pass
    xpl.compile(x=explain_rows, y_pred=y_pred, contributions=contributions)

    top_idx = _top_features_by_mean_abs_shap(shap_values, ctx.get("top_n", 20))
    bar_path = _write_shap_bar_svg(shap_values, feat_names, top_idx, out / "summary_bar.svg")
    beeswarm_path = _write_shap_beeswarm_svg(shap_values, feat_names, top_idx, out / "summary_beeswarm.svg")
    try:
        preds = model.predict(explain_rows) if hasattr(model, "predict") else np.abs(shap_values.values).sum(axis=1)
        row_idx = int(np.argmax(np.abs(preds)))
    except Exception:  # noqa: BLE001
        row_idx = 0
    waterfall_path = _write_shap_waterfall_svg(shap_values, row_idx, feat_names, out / f"waterfall_row_{row_idx}.svg")

    report_path = _write_static_explanation_report(
        out / "report.html",
        title="Model explanation report",
        sections=[
            ("Feature importance", bar_path),
            ("SHAP value distribution", beeswarm_path),
            (f"Row {row_idx} breakdown", waterfall_path),
        ],
    )

    try:
        xpl.save(str(out / "smart_explainer.pkl"))
    except Exception:  # noqa: BLE001 — pickle is a convenience artifact; the HTML report above already succeeded
        pass

    return {
        "engine": "shapash",
        "report": report_path.name,
        "waterfall_row": row_idx,
        "files": [p.name for p in sorted(out.glob("*"))],
    }


# ------------------------------------------------------------------
# TimeSHAP path
# ------------------------------------------------------------------
def run_timeshap(model: Any, data: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Compute TimeSHAP attributions for a sequence model."""
    import numpy as np

    try:
        from timeshap.explainer import local_report  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "TimeSHAP is not installed. Run `python scripts/install_figures.py --tier explain`."
        ) from exc

    out: Path = ctx["out"]
    out.mkdir(parents=True, exist_ok=True)

    sequence_cols: List[str] = ctx.get("sequence_cols") or []

    # Wrap the model in the callable TimeSHAP expects
    def model_fn(x: "np.ndarray") -> "np.ndarray":
        """Adapt the loaded model to the ``(x) -> predictions`` callable TimeSHAP expects."""
        return model(x) if callable(model) else model.predict(x)

    pruning_dict = {"tol": ctx.get("tolerance", 0.025)}
    event_dict = {"rs": 42, "nsamples": 1000}
    feature_dict = {"rs": 42, "nsamples": 1000, "feature_names": sequence_cols}
    cell_dict = {"rs": 42, "nsamples": 1000, "top_x_events": 5, "top_x_feats": 5}

    # local_report returns a dict of dataframes (pruning / event / feature /
    # cell level attributions); the plotting entry points in
    # timeshap.plot are never called (they are matplotlib-backed), so the
    # frames below are re-plotted by hand instead.
    report = local_report(
        model_fn,
        pruning_dict,
        event_dict,
        feature_dict,
        cell_dict,
        data if isinstance(data, np.ndarray) else np.asarray(data),
        entity_col=None,
        baseline=None,
    )

    frames = dict(getattr(report, "items", lambda: [])())  # type: ignore[misc]

    for name, frame in frames.items():
        try:
            frame.to_csv(out / f"timeshap_{name}.csv", index=False)
        except Exception:  # noqa: BLE001
            pass

    (out / "timeshap_report.json").write_text(
        json.dumps({"pruning": pruning_dict, "event": event_dict, "feature": feature_dict, "cell": cell_dict}, indent=2),
        encoding="utf-8",
    )

    rendered: List[str] = []
    for name, frame in frames.items():
        try:
            svg_path = _write_timeshap_frame_svg(frame, name, out / f"timeshap_{name}.svg")
        except Exception as exc:  # noqa: BLE001 — best-effort per frame
            print(f"[warn] could not render timeshap_{name}.svg ({exc})", file=sys.stderr)
            svg_path = None
        if svg_path is not None:
            rendered.append(svg_path.name)

    return {
        "engine": "timeshap",
        "rendered_svgs": rendered,
        "files": [p.name for p in sorted(out.glob("*"))],
    }


def _write_timeshap_frame_svg(frame: Any, name: str, out: Path) -> Optional[Path]:
    """Render one TimeSHAP output frame as a hand-authored SVG bar chart, if it fits.

    ``local_report`` hands back a differently-shaped dataframe per
    pruning / event / feature / cell dict; each carries TimeSHAP's own
    ``Shapley Value`` numeric column alongside a label-like column
    (``Feature``, ``Event``, ``t (Depth)``, or ``Cell`` depending on
    which dict produced it). When a frame carries that shape, it is
    plotted as a horizontal bar chart via the house bar generator.
    Anything else is left as the CSV already written by the caller:
    forcing an unfamiliar table into a chart it does not fit would be
    exactly the kind of invented content the house style forbids.
    """
    if not hasattr(frame, "columns"):
        return None
    value_col = next((c for c in frame.columns if "shapley" in str(c).lower()), None)
    if value_col is None:
        return None
    label_col = next(
        (c for c in frame.columns if str(c).lower() in {"feature", "event", "t (depth)", "cell"}),
        None,
    )
    if label_col is None:
        label_col = next((c for c in frame.columns if c != value_col), None)
    if label_col is None:
        return None
    rows = [{"region": str(r[label_col]), "value": float(r[value_col])} for _, r in frame.iterrows()]
    if not rows:
        return None
    return make_bar.make_bar(
        rows, out=out,
        title=f"TimeSHAP {name} attribution",
        subtitle=f"Shapley value per {str(label_col).lower()}",
        x_label=str(label_col), y_label="Shapley value",
    )


# ------------------------------------------------------------------
# LIME path
# ------------------------------------------------------------------
def run_lime(model: Any, data: Any, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Emit LIME HTML explanations for a black-box classifier."""
    from lime.lime_tabular import LimeTabularExplainer
    import numpy as np

    out: Path = ctx["out"]
    out.mkdir(parents=True, exist_ok=True)

    values = data.values if hasattr(data, "values") else np.asarray(data)
    feat_names = list(data.columns) if hasattr(data, "columns") else [f"f{i}" for i in range(values.shape[1])]

    explainer = LimeTabularExplainer(
        training_data=values,
        feature_names=feat_names,
        discretize_continuous=True,
        random_state=42,
    )

    n_explain = min(ctx.get("n_explain", 10), len(values))
    predict_fn = model.predict_proba if hasattr(model, "predict_proba") else model.predict

    for i in range(n_explain):
        exp = explainer.explain_instance(values[i], predict_fn, num_features=min(15, values.shape[1]))
        exp.save_to_file(str(out / f"lime_row_{i}.html"))

    return {"engine": "lime", "n_explained": n_explain, "files": [p.name for p in sorted(out.glob("*"))]}


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Return the argparse parser for the script."""
    parser = make_parser(
        prog="explain_model",
        description=(
            "Model-explainability dispatcher — SHAP / Shapash / TimeSHAP / "
            "LIME. Auto-picks by model + data shape unless --engine is set."
        ),
    )
    parser.add_argument("--model", required=True,
                        help="Path to a pickled / joblib model. Loading unpickles it, "
                             "which runs arbitrary code — only pass a model you trust.")
    parser.add_argument("--data", required=True, help="Path to CSV / JSON / Parquet / NPY.")
    parser.add_argument("--engine", choices=("auto", "shap", "shapash", "timeshap", "lime"),
                        default="auto", help="Explainability engine (default: auto).")
    parser.add_argument("--report", choices=("none", "shapash"), default="none",
                        help='Add a Shapash HTML report on top of the chosen engine.')
    parser.add_argument("--out", default="./explain", help="Output directory.")
    parser.add_argument("--n-background", type=int, default=100, help="SHAP background sample size.")
    parser.add_argument("--n-explain", type=int, default=500, help="Rows to explain (SHAP) / LIME instances.")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N features for summary + dependence plots.")
    parser.add_argument("--waterfall-row", type=int, default=None, help="Row index for the SHAP waterfall.")
    parser.add_argument("--sequence-cols", default="", help="Comma-separated column names for TimeSHAP.")
    parser.add_argument("--tolerance", type=float, default=0.025, help="TimeSHAP pruning tolerance.")
    parser.add_argument("--link", choices=("identity", "logit"), default="identity",
                        help="SHAP link function (use logit for binary classification).")
    parser.add_argument("--dark", action="store_true", help="Dark-mode plots.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)

    model = load_model(args.model)
    data = load_data(args.data)

    engine = args.engine
    if engine == "auto":
        engine = pick_engine(model, data)
    print(f"[info] engine = {engine}", file=sys.stderr)

    ctx: Dict[str, Any] = {
        "out": Path(args.out),
        "n_background": args.n_background,
        "n_explain": args.n_explain,
        "top_n": args.top_n,
        "waterfall_row": args.waterfall_row,
        "link": args.link,
        "dark": args.dark,
        "sequence_cols": [c.strip() for c in args.sequence_cols.split(",") if c.strip()],
        "tolerance": args.tolerance,
    }

    dispatch = {
        "shap": run_shap,
        "shapash": run_shapash,
        "timeshap": run_timeshap,
        "lime": run_lime,
    }
    summary = dispatch[engine](model, data, ctx)

    if args.report == "shapash" and engine != "shapash":
        summary["shapash_report"] = run_shapash(model, data, ctx)

    summary_path = Path(args.out) / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"wrote {summary_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
