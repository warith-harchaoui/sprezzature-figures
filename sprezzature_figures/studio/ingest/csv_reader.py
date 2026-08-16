"""
CSV ingestion: sniff encoding/delimiter/decimal separator, read with
overridable options, and preview before the user commits (plan §5.1).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from charset_normalizer import from_path
from os_helper import hashfile
from pydantic import BaseModel

from sprezzature_figures.core.dataset import DataWarning

_SNIFF_SAMPLE_BYTES = 65_536
_DEFAULT_NA_VALUES = ["", "NA", "N/A", "null", "NULL", "None", "#N/A", "-"]


class CsvReadOptions(BaseModel):
    encoding: str = "utf-8"
    delimiter: str = ","
    decimal: str = "."
    header_row: int = 0
    na_values: list[str] = _DEFAULT_NA_VALUES


def sniff_csv(path: str | Path, *, sample_bytes: int = _SNIFF_SAMPLE_BYTES) -> CsvReadOptions:
    """Best-effort encoding/delimiter detection, corrigible by the user
    before the file is actually parsed.
    """
    path = Path(path)
    best_match = from_path(path).best()
    encoding = best_match.encoding if best_match is not None else "utf-8"

    with open(path, encoding=encoding, errors="replace") as f:
        sample = f.read(sample_bytes)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    decimal = "," if delimiter == ";" and sample.count(",") > sample.count(".") else "."

    return CsvReadOptions(encoding=encoding, delimiter=delimiter, decimal=decimal)


def read_csv(path: str | Path, options: CsvReadOptions | None = None) -> pd.DataFrame:
    """Read a CSV with explicit (or sniffed) options -- never pandas'
    silent defaults, so encoding/delimiter mistakes are visible and
    correctable rather than producing garbled data.
    """
    resolved = options or sniff_csv(path)
    return pd.read_csv(
        path,
        encoding=resolved.encoding,
        sep=resolved.delimiter,
        decimal=resolved.decimal,
        header=resolved.header_row,
        na_values=resolved.na_values,
        keep_default_na=True,
    )


def preview_csv(
    path: str | Path, options: CsvReadOptions | None = None, n_rows: int = 500
) -> pd.DataFrame:
    resolved = options or sniff_csv(path)
    return pd.read_csv(
        path,
        encoding=resolved.encoding,
        sep=resolved.delimiter,
        decimal=resolved.decimal,
        header=resolved.header_row,
        na_values=resolved.na_values,
        keep_default_na=True,
        nrows=n_rows,
    )


def csv_fingerprint(path: str | Path) -> str:
    return hashfile(str(path))


def csv_warnings(df: pd.DataFrame) -> list[DataWarning]:
    warnings: list[DataWarning] = []
    if df.empty:
        warnings.append(DataWarning(message="file has no data rows", severity="error"))
    if len(df.columns) == 0:
        warnings.append(DataWarning(message="file has no columns", severity="error"))
    return warnings
