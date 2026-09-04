"""
Profile a pandas DataFrame (an in-memory table, the standard shape a
spreadsheet or CSV is loaded into for analysis in Python) into a
DatasetProfile: a synthetic summary sent onward for intent analysis and
recommendation. This module never sends the raw rows anywhere by itself
(plan §1.4); it is left to callers to decide separately whether to attach a
small sample of real rows.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal

import pandas as pd

from sprezzature_figures.core.dataset import ColumnProfile, DatasetProfile, DataWarning

from .semantic_types import detect_semantic_type

# plan §5.4 defaults
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
UI_PREVIEW_ROWS = 500
PROFILING_SAMPLE_ROWS = 100_000
DEFAULT_LLM_SAMPLE_ROWS = 0

_SAMPLE_VALUES_SHOWN = 5
_QUANTILES = (0.25, 0.5, 0.75)


def _json_safe(value: object) -> object:
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def profile_column(series: pd.Series, *, name: str | None = None) -> ColumnProfile:
    col_name = name if name is not None else str(series.name)
    non_null = series.dropna()
    total = len(series)
    null_count = total - len(non_null)
    unique_count = int(non_null.nunique())

    semantic_type = detect_semantic_type(series, name=col_name)

    minimum: float | str | None = None
    maximum: float | str | None = None
    mean: float | None = None
    median: float | None = None
    quantiles: dict[str, float] = {}

    if pd.api.types.is_numeric_dtype(series) and not non_null.empty:
        minimum = float(non_null.min())
        maximum = float(non_null.max())
        mean = float(non_null.mean())
        median = float(non_null.median())
        quantiles = {f"p{int(q * 100)}": float(non_null.quantile(q)) for q in _QUANTILES}
    elif not non_null.empty and semantic_type in ("categorical", "text", "identifier", "datetime"):
        minimum = _json_safe(non_null.min())
        maximum = _json_safe(non_null.max())

    sample_values = [_json_safe(v) for v in non_null.unique()[:_SAMPLE_VALUES_SHOWN]]

    return ColumnProfile(
        name=col_name,
        physical_dtype=str(series.dtype),
        semantic_type=semantic_type,
        null_count=int(null_count),
        null_ratio=(null_count / total) if total else 0.0,
        unique_count=unique_count,
        unique_ratio=(unique_count / len(non_null)) if len(non_null) else 0.0,
        sample_values=sample_values,
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        median=median,
        quantiles=quantiles,
        likely_identifier=semantic_type == "identifier",
        likely_sensitive=semantic_type == "email",
    )


def _coerce_db_driver_types(df: pd.DataFrame) -> pd.DataFrame:
    """Recast ``object``-dtype columns made of raw DB-driver Python types
    (``decimal.Decimal`` for SQL ``NUMERIC``/``DECIMAL``, ``datetime.date``/
    ``datetime.datetime`` for SQL ``DATE``/``TIMESTAMP``) into a dtype pandas
    itself recognizes: ``float64`` for Decimal, ``datetime64`` for date.

    ``pd.DataFrame(rows)`` built from psycopg row dicts keeps these as plain
    Python objects rather than converting them to numpy/pandas-native types,
    so ``pd.api.types.is_numeric_dtype`` / ``is_datetime64_any_dtype`` both
    report ``False`` even though every value is unambiguously a number or a
    date. Left uncorrected this cascades into a wrong analytical goal, a
    candidate list missing the obviously-right chart kind (a monthly revenue
    trend recommending "horizon"/"tree"/"scatter" instead of "line"), and a
    column binding that can silently plot the wrong column (observed: a
    3-column year/month/total_revenue result bound "values" to the
    near-constant "year" column because "total_revenue" wasn't recognized as
    numeric at all). Only touches columns that are actually all-Decimal or
    all-date (or empty/all-null) -- a genuine text/object column is returned
    unchanged.
    """
    # Positional (iloc), not label-based: duplicate column labels make
    # `out[col]` return a DataFrame instead of a Series (same reason
    # profile_dataframe() itself indexes positionally, see its own comment).
    out = df.copy()
    for i in range(out.shape[1]):
        series = out.iloc[:, i]
        if series.dtype != object:
            continue
        non_null = series.dropna()
        if non_null.empty:
            continue
        if non_null.map(lambda v: isinstance(v, Decimal)).all():
            out.isetitem(i, series.astype(float))
        elif non_null.map(lambda v: isinstance(v, date)).all():
            out.isetitem(i, pd.to_datetime(series))
    return out


def _structural_warnings(df: pd.DataFrame) -> list[DataWarning]:
    warnings: list[DataWarning] = []

    seen: set[str] = set()
    for col in df.columns:
        if col in seen:
            warnings.append(
                DataWarning(column=str(col), message="duplicate column name", severity="error")
            )
        seen.add(col)
        if str(col).startswith("Unnamed:"):
            warnings.append(
                DataWarning(
                    column=str(col), message="column has no header name", severity="warning"
                )
            )

    for i, col in enumerate(df.columns):
        if df.iloc[:, i].isna().all():
            warnings.append(
                DataWarning(column=str(col), message="column is entirely empty", severity="warning")
            )

    return warnings


def _data_quality_warnings(df: pd.DataFrame, columns: list[ColumnProfile]) -> list[DataWarning]:
    """Anomalies in the *content*, not the schema: missing values, duplicate
    rows, statistical outliers -- as opposed to `_structural_warnings`, which
    only ever looked at column names/emptiness.

    Built from stats `profile_column` already computes (`null_count`,
    `quantiles`) rather than rescanning the frame, except for the duplicate-row
    check, which is dataset-wide and has no per-column equivalent.

    Regression (TAB-05): a file with a null value, an aberrant value, and a
    duplicate row produced an empty `warnings` list even though these exact
    stats (`null_count`, `p25`/`p75` in `quantiles`) were already sitting in
    the column profiles, unused for anything but display.
    """
    warnings: list[DataWarning] = []

    for col in columns:
        if col.null_count > 0:
            warnings.append(
                DataWarning(
                    column=col.name,
                    message=f"{col.null_count} valeur(s) manquante(s) ({col.null_ratio:.0%})",
                    severity="warning",
                )
            )
        p25, p75 = col.quantiles.get("p25"), col.quantiles.get("p75")
        if p25 is not None and p75 is not None and col.minimum is not None and col.maximum is not None:
            iqr = p75 - p25
            if iqr > 0:
                lower, upper = p25 - 1.5 * iqr, p75 + 1.5 * iqr
                if col.maximum > upper or col.minimum < lower:
                    warnings.append(
                        DataWarning(
                            column=col.name,
                            message=(
                                f"valeur(s) aberrante(s) détectée(s) hors de "
                                f"[{lower:.2f}, {upper:.2f}] (méthode IQR)"
                            ),
                            severity="info",
                        )
                    )

    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        warnings.append(
            DataWarning(
                column=None,
                message=f"{dup_count} ligne(s) en double (contenu identique)",
                severity="warning",
            )
        )

    return warnings


def profile_dataframe(
    df: pd.DataFrame,
    *,
    dataset_id: str,
    fingerprint: str,
    source_name: str,
    sheet_name: str | None = None,
    extra_warnings: list[DataWarning] | None = None,
) -> DatasetProfile:
    """Build a DatasetProfile from an already-loaded DataFrame.

    Profiling runs over the full frame when it's within
    ``PROFILING_SAMPLE_ROWS``; larger frames are sampled so an accidental
    50M-row CSV doesn't hang the UI (plan §5.4).
    """
    sample = (
        df if len(df) <= PROFILING_SAMPLE_ROWS else df.sample(PROFILING_SAMPLE_ROWS, random_state=0)
    )
    sample = _coerce_db_driver_types(sample)

    # Positional indexing (not sample[col]) because duplicate column labels
    # make label-based indexing return a DataFrame instead of a Series.
    columns = [profile_column(sample.iloc[:, i], name=str(col)) for i, col in enumerate(df.columns)]
    warnings = (
        _structural_warnings(df)
        + _data_quality_warnings(sample, columns)
        + (extra_warnings or [])
    )

    return DatasetProfile(
        dataset_id=dataset_id,
        fingerprint=fingerprint,
        source_name=source_name,
        sheet_name=sheet_name,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        warnings=warnings,
    )
