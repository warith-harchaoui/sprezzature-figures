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
# fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "sample.csv"
    p.write_text("city,month,low,high\nMadrid,Jan,2,11\nBerlin,Jan,-3,3\n", encoding="utf-8")
    return p


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


# --------------------------------------------------------------------------
# semantic_types
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("series", "name", "expected"),
    [
        (pd.Series([1, 2, 3, 4]), "value", "numeric"),
        (pd.Series([True, False, True]), "active", "boolean"),
        (pd.Series(["A", "B", "A", "B", "A"]), "group", "categorical"),
        # Regression: bare month names parse "successfully" via pd.to_datetime
        # against an implicit year/day and must not be misread as full dates.
        (pd.Series(["Jan", "Apr", "Jan", "Apr"]), "month", "categorical"),
        (pd.Series(["2024-01-15", "2024-02-20", "2024-03-05", "2024-04-10"]), "event_date", "datetime"),
        (pd.Series(["a@b.com", "c@d.org", "e@f.net", "g@h.io"]), "contact", "email"),
        (pd.Series(["https://a.com", "https://b.com", "http://c.org"]), "link", "url"),
        (pd.Series([48.85, 40.71, 51.50, -33.87]), "latitude", "latitude"),
        (pd.Series([2.35, -74.0, -0.12, 151.2]), "longitude", "longitude"),
        (pd.Series([f"user_{i}" for i in range(50)]), "user_id", "identifier"),
        (
            pd.Series([f"this is a fairly unique free-text sentence number {i}" for i in range(50)]),
            "comment",
            "text",
        ),
    ],
    ids=[
        "numeric",
        "boolean",
        "categorical_strings",
        "month_abbrev_not_datetime",
        "real_dates_datetime",
        "email",
        "url",
        "latitude_by_name_and_range",
        "longitude_by_name_and_range",
        "identifier_by_name_and_uniqueness",
        "free_text_high_cardinality",
    ],
)
def test_detect_semantic_type(series: pd.Series, name: str, expected: str) -> None:
    assert detect_semantic_type(series, name=name) == expected


# --------------------------------------------------------------------------
# csv_reader
# --------------------------------------------------------------------------


def test_csv_read_workflow(sample_csv: Path) -> None:
    """sniff -> read -> preview: a CSV is detected, round-tripped, and truncated."""
    opts = sniff_csv(sample_csv)
    assert opts.delimiter == ","
    assert opts.header_row == 0

    df = read_csv(sample_csv)
    assert list(df.columns) == ["city", "month", "low", "high"]
    assert len(df) == 2

    assert len(preview_csv(sample_csv, n_rows=1)) == 1


def test_csv_fingerprint_is_stable_and_content_sensitive(sample_csv: Path, tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    other.write_text("a,b\n1,2\n", encoding="utf-8")
    assert csv_fingerprint(sample_csv) == csv_fingerprint(sample_csv)
    assert csv_fingerprint(sample_csv) != csv_fingerprint(other)


def test_csv_upload_guards(sample_csv: Path, tmp_path: Path) -> None:
    """Pre-read guards: empty frame and oversized upload both error; a normal
    file under the limit passes clean."""
    empty = csv_warnings(pd.DataFrame())
    assert empty and empty[0].severity == "error"

    big = tmp_path / "big.csv"
    big.write_bytes(b"x" * 1024)
    oversized = validate_upload_size(big, max_bytes=100)
    assert oversized and oversized[0].severity == "error"

    assert validate_upload_size(sample_csv, max_bytes=MAX_UPLOAD_BYTES) == []


# --------------------------------------------------------------------------
# excel_reader
# --------------------------------------------------------------------------


def test_excel_workflow(sample_xlsx: Path) -> None:
    """list sheets -> read named sheet -> structural warnings -> stable fingerprint."""
    assert list_sheets(sample_xlsx) == ["Data", "Other"]

    df = read_excel(sample_xlsx, sheet_name="Data")
    assert len(df) == 3

    messages = " ".join(w.message for w in excel_warnings(sample_xlsx, sheet_name="Data"))
    assert "merged cell" in messages
    assert "totals row" in messages

    assert excel_fingerprint(sample_xlsx) == excel_fingerprint(sample_xlsx)


# --------------------------------------------------------------------------
# clipboard
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_columns"),
    [
        ("city\tvalue\nParis\t10\nLyon\t20", ["city", "value"]),
        ("city,value\nParis,10\nLyon,20", ["city", "value"]),
        ("", []),
    ],
    ids=["tab_separated", "comma_separated", "empty"],
)
def test_parse_clipboard_text(text: str, expected_columns: list[str]) -> None:
    df = parse_clipboard_text(text)
    assert list(df.columns) == expected_columns
    if not expected_columns:
        assert df.empty


def test_clipboard_warnings_and_fingerprint() -> None:
    empty = clipboard_warnings(parse_clipboard_text(""))
    assert empty and empty[0].severity == "error"

    single = clipboard_warnings(parse_clipboard_text("just_one_column\nvalue1\nvalue2"))
    assert any("one column" in i.message for i in single)

    text = "city,value\nParis,10"
    assert clipboard_fingerprint(text) == clipboard_fingerprint(text)


# --------------------------------------------------------------------------
# profiler
# --------------------------------------------------------------------------


def test_profile_dataframe_workflow(sample_csv: Path) -> None:
    """read CSV -> profile: shape, column identity, and numeric column stats."""
    df = read_csv(sample_csv)
    profile = profile_dataframe(
        df, dataset_id="d1", fingerprint=csv_fingerprint(sample_csv), source_name="sample.csv"
    )
    assert profile.row_count == 2
    assert profile.column_count == 4
    assert {c.name for c in profile.columns} == {"city", "month", "low", "high"}

    low = profile.column("low")
    assert low is not None
    assert low.semantic_type == "numeric"
    assert low.minimum == -3.0
    assert low.maximum == 2.0


def test_profile_dataframe_structural_warnings() -> None:
    """Duplicate column names and entirely-empty columns are surfaced as warnings."""
    dup = profile_dataframe(
        pd.DataFrame([[1, 2]], columns=["x", "x"]), dataset_id="d1", fingerprint="f", source_name="dup.csv"
    )
    assert any("duplicate column name" in w.message for w in dup.warnings)

    empty_col = profile_dataframe(
        pd.DataFrame({"a": [1, 2, 3], "b": [None, None, None]}),
        dataset_id="d1",
        fingerprint="f",
        source_name="empty_col.csv",
    )
    assert any("entirely empty" in w.message and w.column == "b" for w in empty_col.warnings)
