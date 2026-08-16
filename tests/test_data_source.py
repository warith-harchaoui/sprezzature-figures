"""
Tests for data_source.load_records, the CLI's local-file loader, and the
``make-figure --data`` wiring that lets a user render their own file
instead of the built-in DEMO_DATA.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sprezzature_figures.data_source import (
    apply_mapping,
    load_records,
    load_stdin_records,
    parse_mapping,
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("d.csv", "parent,name,value\nA,A1,10\nB,B1,20\n"),
        ("d.tsv", "parent\tname\tvalue\nA\tA1\t10\nB\tB1\t20\n"),
    ],
)
def test_load_delimited_coerces_numbers(tmp_path: Path, name: str, text: str) -> None:
    """CSV/TSV cells parse to real ints, not strings, so quantitative roles
    render -- whether pandas is installed or the stdlib fallback runs."""
    rows = load_records(_write(tmp_path, name, text))
    assert rows == [
        {"parent": "A", "name": "A1", "value": 10},
        {"parent": "B", "name": "B1", "value": 20},
    ]


def test_load_csv_stdlib_fallback_when_pandas_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With pandas masked, the stdlib reader still coerces types and reads NA
    tokens / booleans."""
    monkeypatch.setitem(__import__("sys").modules, "pandas", None)
    p = _write(tmp_path, "d.csv", "name,value,flag\nA,3.5,true\nB,-,false\n")
    rows = load_records(p)
    assert rows[0] == {"name": "A", "value": 3.5, "flag": True}
    assert rows[1] == {"name": "B", "value": None, "flag": False}


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("d.json", '[{"name": "A", "value": 1}, {"name": "B", "value": 2}]'),
        ("d.json", '{"data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]}'),
        ("d.jsonl", '{"name": "A", "value": 1}\n{"name": "B", "value": 2}\n'),
    ],
)
def test_load_json_shapes(tmp_path: Path, name: str, text: str) -> None:
    """A bare JSON array, an object wrapping a 'data' array, and JSONL all read
    to the same list of row dicts."""
    rows = load_records(_write(tmp_path, name, text))
    assert rows == [{"name": "A", "value": 1}, {"name": "B", "value": 2}]


@pytest.mark.parametrize(
    ("name", "text", "match"),
    [
        ("d.xml", "<x/>", "unsupported data format"),
        ("d.json", "[1, 2, 3]", "object/mapping"),
        ("d.json", "{}", "expected a JSON array"),
        ("d.csv", "", "no data rows"),
    ],
)
def test_load_records_rejects_bad_input(tmp_path: Path, name: str, text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        load_records(_write(tmp_path, name, text))


def test_load_records_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_records(tmp_path / "nope.csv")


@pytest.mark.parametrize(
    "text",
    [
        '[{"name": "A", "value": 1}, {"name": "B", "value": 2}]',
        '{"data": [{"name": "A", "value": 1}, {"name": "B", "value": 2}]}',
        '{"name": "A", "value": 1}\n{"name": "B", "value": 2}\n',
        "name,value\nA,1\nB,2\n",
        "name\tvalue\nA\t1\nB\t2\n",
    ],
)
def test_load_stdin_sniffs_json_jsonl_and_delimited(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--data -` reads stdin and detects the shape from content: JSON array,
    'data'-wrapped object, JSONL, and CSV/TSV all reach the same row dicts."""
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    assert load_stdin_records() == [{"name": "A", "value": 1}, {"name": "B", "value": 2}]


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("", "no data"),
        ("   \n  ", "no data"),
        ("[1, 2, 3]", "object/mapping"),
        ("{}", "expected a JSON array"),
    ],
)
def test_load_stdin_rejects_bad_input(
    text: str, match: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(text))
    with pytest.raises(ValueError, match=match):
        load_stdin_records()


def test_parse_mapping_valid_and_invalid() -> None:
    assert parse_mapping(["value=GDP", "region=Country"]) == {"value": "GDP", "region": "Country"}
    for bad in ["novalue", "role=", "=col", ""]:
        with pytest.raises(ValueError, match="role=column"):
            parse_mapping([bad])


def test_apply_mapping_aliases_columns_and_keeps_originals() -> None:
    rows = [{"Region": "N", "GDP": 42}, {"Region": "S", "GDP": 28}]
    out = apply_mapping(rows, {"region": "Region", "value": "GDP"})
    assert out[0] == {"Region": "N", "GDP": 42, "region": "N", "value": 42}


def test_apply_mapping_empty_is_identity_and_missing_column_raises() -> None:
    rows = [{"a": 1}]
    assert apply_mapping(rows, {}) is rows
    with pytest.raises(ValueError, match="not in data: Nope"):
        apply_mapping(rows, {"value": "Nope"})


@pytest.mark.slow
def test_make_figure_cli_renders_from_data_file(tmp_path: Path) -> None:
    """End to end: `make-figure treemap --data d.csv --out x.svg` renders the
    user's file, not DEMO_DATA."""
    import subprocess
    import sys

    data = _write(tmp_path, "d.csv", "parent,name,value\nA,A1,10\nB,B1,20\n")
    out = tmp_path / "x.svg"
    proc = subprocess.run(
        [sys.executable, "-m", "sprezzature_figures.make_figure", "treemap", "--data", str(data), "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.slow
def test_make_figure_cli_map_binds_mismatched_columns(tmp_path: Path) -> None:
    """`--map role=column` lets a file whose headers differ from the figure's
    roles render, instead of failing role validation."""
    import subprocess
    import sys

    data = _write(tmp_path, "d.csv", "Region,GDP\nNorth,42\nSouth,28\n")
    out = tmp_path / "x.png"
    proc = subprocess.run(
        [
            sys.executable, "-m", "sprezzature_figures.make_figure", "bar",
            "--data", str(data), "--map", "region=Region", "--map", "value=GDP",
            "--out", str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists() and out.read_bytes()[:4] == b"\x89PNG"
