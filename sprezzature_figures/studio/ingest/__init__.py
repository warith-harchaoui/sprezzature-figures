"""
sprezzature_figures.studio.ingest — CSV/XLSX/clipboard import and profiling.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from .clipboard import clipboard_fingerprint, clipboard_warnings, parse_clipboard_text
from .csv_reader import (
    CsvReadOptions,
    csv_fingerprint,
    csv_warnings,
    preview_csv,
    read_csv,
    sniff_csv,
)
from .excel_reader import excel_fingerprint, excel_warnings, list_sheets, preview_excel, read_excel
from .profiler import (
    DEFAULT_LLM_SAMPLE_ROWS,
    MAX_UPLOAD_BYTES,
    PROFILING_SAMPLE_ROWS,
    UI_PREVIEW_ROWS,
    profile_column,
    profile_dataframe,
)
from .semantic_types import detect_semantic_type
from .validation import validate_upload_size

__all__ = [
    "DEFAULT_LLM_SAMPLE_ROWS",
    "MAX_UPLOAD_BYTES",
    "PROFILING_SAMPLE_ROWS",
    "UI_PREVIEW_ROWS",
    "CsvReadOptions",
    "clipboard_fingerprint",
    "clipboard_warnings",
    "csv_fingerprint",
    "csv_warnings",
    "detect_semantic_type",
    "excel_fingerprint",
    "excel_warnings",
    "list_sheets",
    "parse_clipboard_text",
    "preview_csv",
    "preview_excel",
    "profile_column",
    "profile_dataframe",
    "read_csv",
    "read_excel",
    "sniff_csv",
    "validate_upload_size",
]
