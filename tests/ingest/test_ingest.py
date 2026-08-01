"""
Tests for sprezzature_figures.studio.ingest: CSV/XLSX/clipboard readers,
semantic type detection, and the profiler.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pytest

from sprezzature_figures.studio.ingest import (
    clipboard_fingerprint,
    clipboard_warnings,
    csv_fingerprint,
    csv_warnings,
    excel_fingerprint,
    excel_warnings,
    list_sheets,
    parse_clipboard_text,
    preview_csv,
    profile_dataframe,
    read_csv,
    read_excel,
    sniff_csv,
    validate_upload_size,
)
from sprezzature_figures.studio.ingest.profiler import MAX_UPLOAD_BYTES
from sprezzature_figures.studio.ingest.semantic_types import detect_semantic_type

# --------------------------------------------------------------------------
# semantic_types
# --------------------------------------------------------------------------


def test_detect_numeric() -> None:
    assert detect_semantic_type(pd.Series([1, 2, 3, 4]), name="value") == "numeric"


def test_detect_categorical_low_cardinality_strings() -> None:
    assert detect_semantic_type(pd.Series(["A", "B", "A", "B", "A"]), name="group") == "categorical"


def test_detect_month_abbreviations_are_categorical_not_datetime() -> None:
    """Regression: bare month names parse "successfully" via pd.to_datetime
    against an implicit year/day and must not be misread as full dates.
    """
    assert detect_semantic_type(pd.Series(["Jan", "Apr", "Jan", "Apr"]), name="month") == "categorical"


def test_detect_real_dates_as_datetime() -> None:
    dates = pd.Series(["2024-01-15", "2024-02-20", "2024-03-05", "2024-04-10"])
    assert detect_semantic_type(dates, name="event_date") == "datetime"


def test_detect_email() -> None:
    emails = pd.Series(["a@b.com", "c@d.org", "e@f.net", "g@h.io"])
    assert detect_semantic_type(emails, name="contact") == "email"


def test_detect_url() -> None:
    urls = pd.Series(["https://a.com", "https://b.com", "http://c.org"])
    assert detect_semantic_type(urls, name="link") == "url"


def test_detect_latitude_by_name_and_range() -> None:
    lat = pd.Series([48.85, 40.71, 51.50, -33.87])
    assert detect_semantic_type(lat, name="latitude") == "latitude"


def test_detect_longitude_by_name_and_range() -> None:
    lon = pd.Series([2.35, -74.0, -0.12, 151.2])
    assert detect_semantic_type(lon, name="longitude") == "longitude"


def test_detect_identifier_by_name_and_uniqueness() -> None:
    ids = pd.Series([f"user_{i}" for i in range(50)])
    assert detect_semantic_type(ids, name="user_id") == "identifier"


def test_detect_boolean() -> None:
    assert detect_semantic_type(pd.Series([True, False, True]), name="active") == "boolean"


def test_detect_free_text_high_cardinality() -> None:
    text = pd.Series([f"this is a fairly unique free-text sentence number {i}" for i in range(50)])
    assert detect_semantic_type(text, name="comment") == "text"


# --------------------------------------------------------------------------
# csv_reader
# --------------------------------------------------------------------------


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "sample.csv"
    p.write_text("city,month,low,high\nMadrid,Jan,2,11\nBerlin,Jan,-3,3\n", encoding="utf-8")
    return p


def test_sniff_csv_detects_comma_and_utf8(sample_csv: Path) -> None:
    opts = sniff_csv(sample_csv)
    assert opts.delimiter == ","
    assert opts.header_row == 0


def test_read_csv_round_trips_data(sample_csv: Path) -> None:
    df = read_csv(sample_csv)
    assert list(df.columns) == ["city", "month", "low", "high"]
    assert len(df) == 2


def test_preview_csv_respects_row_limit(sample_csv: Path) -> None:
    df = preview_csv(sample_csv, n_rows=1)
    assert len(df) == 1


def test_csv_fingerprint_is_stable(sample_csv: Path) -> None:
    assert csv_fingerprint(sample_csv) == csv_fingerprint(sample_csv)


def test_csv_fingerprint_differs_for_different_content(sample_csv: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    other.write_text("a,b\n1,2\n", encoding="utf-8")
    assert csv_fingerprint(sample_csv) != csv_fingerprint(other)


def test_csv_warnings_flags_empty_dataframe() -> None:
    assert csv_warnings(pd.DataFrame()) and csv_warnings(pd.DataFrame())[0].severity == "error"


def test_validate_upload_size_flags_oversized_file(tmp_path: Path) -> None:
    big = tmp_path / "big.csv"
    big.write_bytes(b"x" * 1024)
    issues = validate_upload_size(big, max_bytes=100)
    assert issues and issues[0].severity == "error"


def test_validate_upload_size_passes_under_limit(sample_csv: Path) -> None:
    assert validate_upload_size(sample_csv, max_bytes=MAX_UPLOAD_BYTES) == []


# --------------------------------------------------------------------------
# excel_reader
# --------------------------------------------------------------------------


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    path = tmp_path / "sample.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["city", "value"])
    ws.append(["Paris", 10])
    ws.append(["Lyon", 20])
    ws.append(["Total", 30])
    ws.merge_cells("A1:B1")
    wb.create_sheet("Other")
    wb.save(path)
    return path


def test_list_sheets(sample_xlsx: Path) -> None:
    assert list_sheets(sample_xlsx) == ["Data", "Other"]


def test_read_excel_reads_named_sheet(sample_xlsx: Path) -> None:
    df = read_excel(sample_xlsx, sheet_name="Data")
    assert len(df) == 3


def test_excel_warnings_detects_merged_cells_and_totals_row(sample_xlsx: Path) -> None:
    warnings = excel_warnings(sample_xlsx, sheet_name="Data")
    messages = " ".join(w.message for w in warnings)
    assert "merged cell" in messages
    assert "totals row" in messages


def test_excel_fingerprint_is_stable(sample_xlsx: Path) -> None:
    assert excel_fingerprint(sample_xlsx) == excel_fingerprint(sample_xlsx)


# --------------------------------------------------------------------------
# clipboard
# --------------------------------------------------------------------------


def test_parse_clipboard_tab_separated() -> None:
    df = parse_clipboard_text("city\tvalue\nParis\t10\nLyon\t20")
    assert list(df.columns) == ["city", "value"]
    assert len(df) == 2


def test_parse_clipboard_comma_separated() -> None:
    df = parse_clipboard_text("city,value\nParis,10\nLyon,20")
    assert list(df.columns) == ["city", "value"]


def test_parse_clipboard_empty_text_returns_empty_dataframe() -> None:
    assert parse_clipboard_text("").empty


def test_clipboard_warnings_flags_empty_paste() -> None:
    issues = clipboard_warnings(parse_clipboard_text(""))
    assert issues and issues[0].severity == "error"


def test_clipboard_warnings_flags_single_column() -> None:
    df = parse_clipboard_text("just_one_column\nvalue1\nvalue2")
    issues = clipboard_warnings(df)
    assert any("one column" in i.message for i in issues)


def test_clipboard_fingerprint_stable_for_same_text() -> None:
    text = "city,value\nParis,10"
    assert clipboard_fingerprint(text) == clipboard_fingerprint(text)


# --------------------------------------------------------------------------
# profiler
# --------------------------------------------------------------------------


def test_profile_dataframe_builds_correct_shape(sample_csv: Path) -> None:
    df = read_csv(sample_csv)
    profile = profile_dataframe(
        df, dataset_id="d1", fingerprint=csv_fingerprint(sample_csv), source_name="sample.csv"
    )
    assert profile.row_count == 2
    assert profile.column_count == 4
    assert {c.name for c in profile.columns} == {"city", "month", "low", "high"}


def test_profile_dataframe_flags_duplicate_column_names() -> None:
    df = pd.DataFrame([[1, 2]], columns=["x", "x"])
    profile = profile_dataframe(df, dataset_id="d1", fingerprint="f", source_name="dup.csv")
    assert any("duplicate column name" in w.message for w in profile.warnings)


def test_profile_dataframe_flags_entirely_empty_column() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [None, None, None]})
    profile = profile_dataframe(df, dataset_id="d1", fingerprint="f", source_name="empty_col.csv")
    assert any("entirely empty" in w.message and w.column == "b" for w in profile.warnings)


def test_profile_column_numeric_stats(sample_csv: Path) -> None:
    df = read_csv(sample_csv)
    profile = profile_dataframe(
        df, dataset_id="d1", fingerprint=csv_fingerprint(sample_csv), source_name="sample.csv"
    )
    low = profile.column("low")
    assert low is not None
    assert low.semantic_type == "numeric"
    assert low.minimum == -3.0
    assert low.maximum == 2.0
