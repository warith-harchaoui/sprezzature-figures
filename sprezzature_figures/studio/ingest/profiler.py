"""
Profile a pandas DataFrame into a DatasetProfile: the synthetic summary sent
onward for intent analysis and recommendation. Never sends raw rows anywhere
by itself (plan §1.4) -- callers decide separately whether to attach a small
sample.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import math

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


def _structural_warnings(df: pd.DataFrame) -> list[DataWarning]:
    warnings: list[DataWarning] = []

    seen: set[str] = set()
    for col in df.columns:
        if col in seen:
            warnings.append(DataWarning(column=str(col), message="duplicate column name", severity="error"))
        seen.add(col)
        if str(col).startswith("Unnamed:"):
            warnings.append(DataWarning(column=str(col), message="column has no header name", severity="warning"))

    for i, col in enumerate(df.columns):
        if df.iloc[:, i].isna().all():
            warnings.append(DataWarning(column=str(col), message="column is entirely empty", severity="warning"))

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
    sample = df if len(df) <= PROFILING_SAMPLE_ROWS else df.sample(PROFILING_SAMPLE_ROWS, random_state=0)

    # Positional indexing (not sample[col]) because duplicate column labels
    # make label-based indexing return a DataFrame instead of a Series.
    columns = [profile_column(sample.iloc[:, i], name=str(col)) for i, col in enumerate(df.columns)]
    warnings = _structural_warnings(df) + (extra_warnings or [])

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
