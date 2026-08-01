"""
Parse cells copied from Excel/LibreOffice/Google Sheets and pasted as text
(plan §5.3). Spreadsheet paste is tab-separated with the header on the first
line; falls back to comma/semicolon for plain CSV-shaped paste.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import csv
import io

import pandas as pd
from os_helper import hash_string

from sprezzature_figures.core.dataset import DataWarning


def _sniff_delimiter(text: str) -> str:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if "\t" in first_line:
        return "\t"
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def parse_clipboard_text(text: str, *, header: bool = True) -> pd.DataFrame:
    text = text.strip("\n")
    if not text.strip():
        return pd.DataFrame()
    delimiter = _sniff_delimiter(text)
    return pd.read_csv(io.StringIO(text), sep=delimiter, header=0 if header else None)


def clipboard_fingerprint(text: str) -> str:
    return hash_string(text)


def clipboard_warnings(df: pd.DataFrame) -> list[DataWarning]:
    warnings: list[DataWarning] = []
    if df.empty:
        warnings.append(DataWarning(message="pasted content produced no data rows", severity="error"))
    if len(df.columns) == 1:
        warnings.append(
            DataWarning(
                message="only one column detected -- check that the paste used tab or comma separation",
                severity="warning",
            )
        )
    return warnings
