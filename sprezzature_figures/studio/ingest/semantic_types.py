"""
Rule-based detection of an imported column's semantic type (numeric,
categorical, text, datetime, boolean, identifier, latitude, longitude,
percentage, currency, url, email; plan §5.5): fixed rules decide the type,
with no language model involved in the decision itself. A model may later
*suggest* a correction, but it never overrides this detection without
the user explicitly confirming the change.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re

import pandas as pd

from sprezzature_figures.core.dataset import SemanticType

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)

_LAT_NAME_RE = re.compile(r"(^|_)lat(itude)?($|_)", re.IGNORECASE)
_LON_NAME_RE = re.compile(r"(^|_)lon(gitude)?($|_)", re.IGNORECASE)
_ID_NAME_RE = re.compile(r"(^|_)(id|uuid|guid)($|_)", re.IGNORECASE)
_PERCENT_NAME_RE = re.compile(r"pct|percent|%|rate$|ratio$", re.IGNORECASE)
# Les codes devise à 3 lettres doivent être délimités (^|_ ... $|_) : en
# sous-chaîne libre, "eur" matche n'importe quel mot français qui le
# contient (valeur, employeur, longueur, hauteur, ingénieur...), classant
# à tort la colonne "currency" au lieu de "numeric" -- bug réel mesuré :
# une colonne "valeur" faisait échouer la sélection de graphique (ecdf
# choisi au lieu de line pour une tendance temporelle), cf. TAB-03.
_CURRENCY_NAME_RE = re.compile(
    r"price|cost|revenue|amount|salary|budget|spend|(^|_)(usd|eur|gbp)($|_)",
    re.IGNORECASE,
)

_IDENTIFIER_UNIQUE_RATIO = 0.98
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.5
_SAMPLE_SIZE = 200


def _non_null_sample(series: pd.Series, n: int = _SAMPLE_SIZE) -> pd.Series:
    non_null = series.dropna()
    return non_null.sample(min(n, len(non_null)), random_state=0) if len(non_null) > n else non_null


def _matches_ratio(sample: pd.Series, pattern: re.Pattern[str], threshold: float = 0.9) -> bool:
    if sample.empty:
        return False
    as_str = sample.astype(str)
    hits = as_str.str.match(pattern).sum()
    return (hits / len(as_str)) >= threshold


def detect_semantic_type(series: pd.Series, *, name: str | None = None) -> SemanticType:
    """Best-effort semantic type for one column, using dtype, column name
    hints, and a content sample -- never the whole column for large data.
    """
    col_name = name if name is not None else (series.name or "")
    sample = _non_null_sample(series)

    if pd.api.types.is_bool_dtype(series):
        return "boolean"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"

    if pd.api.types.is_numeric_dtype(series):
        unique_ratio = series.nunique(dropna=True) / max(len(series.dropna()), 1)
        if _LAT_NAME_RE.search(col_name) and sample.between(-90, 90).all():
            return "latitude"
        if _LON_NAME_RE.search(col_name) and sample.between(-180, 180).all():
            return "longitude"
        if _ID_NAME_RE.search(col_name) and unique_ratio >= _IDENTIFIER_UNIQUE_RATIO:
            return "identifier"
        if _PERCENT_NAME_RE.search(col_name):
            return "percentage"
        if _CURRENCY_NAME_RE.search(col_name):
            return "currency"
        return "numeric"

    # Object/string-like column: try datetime parsing, then content patterns.
    if not sample.empty:
        # Require digits in the raw strings before trusting to_datetime: bare
        # month/weekday names ("Jan", "Mon") parse "successfully" against an
        # implicit current year/day, which would otherwise misclassify a
        # plain categorical month column as a full datetime.
        has_digit_ratio = sample.astype(str).str.contains(r"\d", regex=True).mean()
        if has_digit_ratio >= 0.9:
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.9:
                return "datetime"
        if _matches_ratio(sample, _EMAIL_RE):
            return "email"
        if _matches_ratio(sample, _URL_RE):
            return "url"

    unique_ratio = series.nunique(dropna=True) / max(len(series.dropna()), 1)
    if _ID_NAME_RE.search(col_name) and unique_ratio >= _IDENTIFIER_UNIQUE_RATIO:
        return "identifier"
    if unique_ratio >= _IDENTIFIER_UNIQUE_RATIO and len(series.dropna()) > 20 and not sample.empty:
        # Near-unique short tokens (no spaces) look like identifiers; near-unique
        # multi-word values are more likely free text (e.g. distinct comments).
        avg_tokens = sample.astype(str).str.split().str.len().mean()
        if avg_tokens <= 2:
            return "identifier"
    if unique_ratio <= _CATEGORICAL_MAX_UNIQUE_RATIO:
        return "categorical"
    return "text"
