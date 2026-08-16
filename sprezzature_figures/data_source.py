"""
data_source -- load a local data file into the ``list[dict]`` shape every
figure generator expects.

This is the CLI's answer to "I have my own CSV/JSON, not just the built-in
DEMO_DATA". It stays dependency-light on purpose: the base install carries no
pandas, so CSV/TSV parsing falls back to the stdlib ``csv`` module with
best-effort numeric coercion, and JSON/JSONL uses stdlib ``json``. When pandas
*is* present (the ``studio``/``dataviz`` extras), it is preferred for CSVs
because its type inference and delimiter handling are sturdier.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

# Cells matching one of these (case-insensitive) become ``None`` rather than a
# literal string, mirroring the CSV reader in studio.ingest.
_NA_TOKENS = {"", "na", "n/a", "null", "none", "#n/a", "-"}


def _coerce_scalar(value: str) -> Any:
    """Turn one raw CSV cell into int/float/bool/None/str.

    The stdlib ``csv`` reader hands back every cell as a string; figure
    generators expect real numbers for quantitative roles. Try the narrowest
    type that fits, in order, and fall back to the original string.
    """
    stripped = value.strip()
    if stripped.lower() in _NA_TOKENS:
        return None
    if stripped.lower() in ("true", "false"):
        return stripped.lower() == "true"
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return value


def _load_csv_stdlib(path: Path, delimiter: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if reader.fieldnames is None:
            return []
        return [
            {k: _coerce_scalar(v) if isinstance(v, str) else v for k, v in row.items()}
            for row in reader
        ]


def _load_csv_pandas(path: Path) -> list[dict[str, Any]] | None:
    """Prefer pandas when it is installed: better dtype inference and it
    sniffs the delimiter via ``sep=None``/``engine='python'``. Returns
    ``None`` when pandas is unavailable so the caller can fall back.
    """
    try:
        import pandas as pd
    except ImportError:
        return None
    try:
        df = pd.read_csv(path, sep=None, engine="python")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, csv.Error):
        # Empty or unsniffable file: let the stdlib path produce the
        # canonical "no data rows" / delimiter fallback behaviour.
        return None
    # NaN -> None so JSON-shaped consumers and Vega see nulls, not float('nan').
    return df.where(df.notna(), None).to_dict(orient="records")


def _sniff_delimiter(path: Path) -> str:
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(65_536)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return "\t" if path.suffix.lower() == ".tsv" else ","


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Read a local data file into a list of row dicts.

    Supported formats, chosen by extension:

    - ``.json``  -- a JSON array of objects, or a single object wrapping a
      ``"data"`` / ``"rows"`` array.
    - ``.jsonl`` / ``.ndjson`` -- one JSON object per line.
    - ``.csv`` / ``.tsv`` / ``.txt`` -- delimited text; pandas is used when
      available, otherwise the stdlib reader with numeric coercion.

    Parameters
    ----------
    path : str or Path
        The file to read.

    Returns
    -------
    list[dict]
        Row records ready to hand to :func:`sprezzature_figures.make_figure`.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the extension is unsupported, or the file parses to something other
        than a list of objects.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".json":
        records = _unwrap_json_array(json.loads(path.read_text(encoding="utf-8")), path.name)
    elif suffix in (".jsonl", ".ndjson"):
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif suffix in (".csv", ".tsv", ".txt"):
        records = _load_csv_pandas(path)
        if records is None:
            records = _load_csv_stdlib(path, _sniff_delimiter(path))
    else:
        raise ValueError(
            f"unsupported data format {suffix!r} for {path.name}; use .csv, .tsv, .json, or .jsonl"
        )

    return _validate_records(records, path.name)


def _unwrap_json_array(payload: Any, source: str) -> list[Any]:
    """Return the row array from a parsed JSON payload.

    Accepts either a bare array of objects or a single object that wraps the
    rows under a ``data``/``rows``/``records``/``values`` key -- the two shapes
    real-world JSON exports come in. Anything else is a usage error.
    """
    if isinstance(payload, dict):
        for key in ("data", "rows", "records", "values"):
            if isinstance(payload.get(key), list):
                return payload[key]
    if not isinstance(payload, list):
        raise ValueError(
            f"{source}: expected a JSON array of row objects (or an object with a "
            "'data'/'rows' array), got a top-level " + type(payload).__name__
        )
    return payload


def _validate_records(records: list[Any], source: str) -> list[dict[str, Any]]:
    """Guard the invariant every caller relies on: a non-empty list of dicts."""
    if not all(isinstance(row, dict) for row in records):
        raise ValueError(f"{source}: every row must be an object/mapping, not a bare value")
    if not records:
        raise ValueError(f"{source}: no data rows found")
    return records


def load_stdin_records() -> list[dict[str, Any]]:
    """Read row records piped to standard input, sniffing the format from content.

    Backs the ``--data -`` form of the render/recommend CLIs, so data can be
    piped straight in (``curl ... | make-figure bar --data -``) with no temp
    file. Standard input has no filename to key the format off, so the shape is
    detected from the bytes: a leading ``[`` or ``{`` is parsed as JSON; failing
    that, if every non-blank line is its own JSON object it is JSONL; otherwise
    it is delimited text (delimiter sniffed, cells coerced) exactly like a CSV.

    Raises
    ------
    ValueError
        If standard input is empty or parses to something other than rows.
    """
    text = sys.stdin.read()
    stripped = text.strip()
    if not stripped:
        raise ValueError("stdin: no data received (did you pipe a file in?)")

    # JSONL first: several compact objects, one per line, each starting with '{'.
    # This has to be checked before the single-JSON branch, since a JSONL stream
    # also starts with '{' but is not one parseable JSON document. A pretty-
    # printed array/object fails the all-lines-start-with-'{' test and falls
    # through to the single-JSON branch below.
    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) > 1 and all(line.lstrip().startswith("{") for line in lines):
        try:
            records = [json.loads(line) for line in lines]
        except json.JSONDecodeError:
            pass  # not JSONL after all; fall through to single-JSON / delimited
        else:
            return _validate_records(records, "stdin")

    if stripped[0] in "[{":
        return _validate_records(_unwrap_json_array(json.loads(stripped), "stdin"), "stdin")

    try:
        delimiter = csv.Sniffer().sniff(text[:65_536], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    records = [
        {k: _coerce_scalar(v) if isinstance(v, str) else v for k, v in row.items()}
        for row in reader
    ]
    return _validate_records(records, "stdin")


def parse_mapping(pairs: list[str]) -> dict[str, str]:
    """Parse ``--map role=column`` CLI strings into a ``{role: column}`` dict.

    Raises ``ValueError`` on a token missing the ``=`` or with an empty side.
    """
    mapping: dict[str, str] = {}
    for pair in pairs:
        role, sep, column = pair.partition("=")
        role, column = role.strip(), column.strip()
        if not sep or not role or not column:
            raise ValueError(f"--map expects role=column, got {pair!r}")
        mapping[role] = column
    return mapping


def apply_mapping(records: list[dict[str, Any]], mapping: dict[str, str]) -> list[dict[str, Any]]:
    """Alias source columns to the role names a figure expects.

    For each ``{role: column}`` entry, add a ``role``-named key to every row
    carrying that column's value, keeping the originals. This lets a file whose
    headers don't match a figure's role names still render, without editing the
    file. Returns ``records`` unchanged when ``mapping`` is empty.

    Raises
    ------
    ValueError
        If a mapped source column is absent from the data.
    """
    if not mapping:
        return records
    columns = set(records[0]) if records else set()
    missing = sorted({col for col in mapping.values() if col not in columns})
    if missing:
        raise ValueError(f"--map source column(s) not in data: {', '.join(missing)}")
    return [{**row, **{role: row.get(col) for role, col in mapping.items()}} for row in records]
