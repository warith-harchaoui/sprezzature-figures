"""
Tests for redraw(): a picture of somebody else's chart in, a figure out.

Every test here scripts the vision model with FakeLLMClient, so the suite
never needs Ollama or a network. What is worth testing is not the model --
it is the two promises made around it:

1. The model cannot name a chart kind it was not offered.
2. Numbers are never invented. `data_origin` says where they came from,
   and the fall-through to sample data is captioned on the figure itself.

Tests that render a real SVG are marked @pytest.mark.slow, like the ones
in test_make_figure.py and test_api.py.

Author
------
Warith HARCHAOUI <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest

from sprezzature_figures.redraw import _image_bytes, redraw, rows_from_reading
from sprezzature_figures.studio.assistant.fake_client import FakeLLMClient
from sprezzature_figures.studio.assistant.read_chart import (
    ChartReadingError,
    candidate_lines,
    read_chart,
)
from sprezzature_figures.studio.assistant.schemas import ChartReading, ReadSeries, VisualIssue

# The 8-byte PNG signature is all _image_bytes() inspects; a real raster
# would only make the fixtures heavier.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">' b"<rect width='40' height='20' fill='#333'/></svg>"


def reading(**overrides: Any) -> ChartReading:
    """A plausible reading of a bar chart, overridable field by field."""
    base: dict[str, Any] = {
        "kind": "bar",
        "kind_confidence": "high",
        "drawn_as": "flat bars, one per region, no gridlines",
        "what_it_shows": "Revenue by region.",
        "title": "Revenue by region",
        "suggested_title": "The North carries two thirds of revenue",
        "series": [],
        "values_are_readable": False,
        "issues": [
            VisualIssue(
                category="legend",
                severity="low",
                observation="The legend sits below the notes.",
                suggested_action="Name the marks where they are.",
            ),
            VisualIssue(
                category="contrast",
                severity="critical",
                observation="Two warm hues carry the whole distinction.",
                suggested_action="Separate the series by fill, not only by hue.",
            ),
        ],
    }
    base.update(overrides)
    return ChartReading.model_validate(base)


def client_for(*responses: Any) -> FakeLLMClient:
    return FakeLLMClient(list(responses))


# --------------------------------------------------------------------------
# Reading the image file itself
# --------------------------------------------------------------------------


def test_png_passes_through_untouched() -> None:
    assert _image_bytes(PNG) == PNG


def test_svg_input_is_rasterised() -> None:
    """An SVG is a chart too. resvg-py is a core dependency, so this is free."""
    out = _image_bytes(SVG)
    assert out.startswith(b"\x89PNG\r\n\x1a\n")


def test_pdf_is_refused_by_name(tmp_path: Path) -> None:
    """The one refusal people hit on purpose says what to do instead."""
    pdf = tmp_path / "chart.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    with pytest.raises(ValueError, match="PDF"):
        _image_bytes(pdf)


def test_unrecognised_bytes_are_refused() -> None:
    with pytest.raises(ValueError, match="unrecognised image"):
        _image_bytes(b"this is not a picture of anything")


def test_path_and_bytes_are_equivalent(tmp_path: Path) -> None:
    p = tmp_path / "chart.png"
    p.write_bytes(PNG)
    assert _image_bytes(p) == _image_bytes(PNG) == _image_bytes(str(p))


# --------------------------------------------------------------------------
# The model may not name a kind it was not offered
# --------------------------------------------------------------------------


def test_kind_outside_the_candidate_list_is_refused() -> None:
    from sprezzature_figures.catalog import get_figure_definition

    only_bar = [get_figure_definition("bar")]
    with pytest.raises(ChartReadingError, match="not one of the"):
        read_chart(client_for(reading(kind="treemap")), PNG, candidates=only_bar)


def test_invented_kind_is_refused() -> None:
    with pytest.raises(ChartReadingError, match="not one of the"):
        read_chart(client_for(reading(kind="spiral-of-doom")), PNG)


def test_alias_is_resolved_to_the_canonical_kind() -> None:
    """A model answering 'Bar' or 'bar chart' is answering correctly."""
    result = read_chart(client_for(reading(kind="Bar")), PNG)
    assert result.kind == "bar"


def test_candidate_list_names_every_kind_once() -> None:
    from sprezzature_figures.catalog import get_registry

    stable = [d for d in get_registry() if d.status == "stable"]
    lines = candidate_lines(stable).splitlines()
    assert len(lines) == len(stable)
    assert all(line.startswith("- ") for line in lines)


def test_the_image_actually_reaches_the_model() -> None:
    """A reading that never looked at the picture would be worthless."""
    fake = client_for(reading())
    read_chart(fake, PNG)
    assert len(fake.calls) == 1
    assert "candidate" in fake.calls[0]["prompt"].lower()


# --------------------------------------------------------------------------
# Numbers are never invented
# --------------------------------------------------------------------------


def test_unreadable_values_yield_no_rows() -> None:
    """The normal case: a chart without data labels does not carry its numbers."""
    r = reading(
        values_are_readable=False,
        series=[ReadSeries(name="Revenue", labels=["N", "S"], values=[10.0, 20.0])],
    )
    assert rows_from_reading(r, "bar") is None


def test_readable_values_become_rows_under_the_right_role_names() -> None:
    r = reading(
        values_are_readable=True,
        series=[ReadSeries(name="Revenue", labels=["North", "South"], values=[61.0, 39.0])],
    )
    assert rows_from_reading(r, "bar") == [
        {"region": "North", "value": 61.0},
        {"region": "South", "value": 39.0},
    ]


def test_misaligned_labels_and_values_yield_no_rows() -> None:
    r = reading(
        values_are_readable=True,
        series=[ReadSeries(name="Revenue", labels=["North", "South"], values=[61.0])],
    )
    assert rows_from_reading(r, "bar") is None


def test_two_series_yield_no_rows() -> None:
    """Two series cannot be bound to a one-value figure without guessing."""
    r = reading(
        values_are_readable=True,
        series=[
            ReadSeries(name="2024", labels=["N", "S"], values=[1.0, 2.0]),
            ReadSeries(name="2025", labels=["N", "S"], values=[3.0, 4.0]),
        ],
    )
    assert rows_from_reading(r, "bar") is None


def test_a_figure_needing_three_roles_yields_no_rows() -> None:
    r = reading(
        kind="bar-grouped",
        values_are_readable=True,
        series=[ReadSeries(name="x", labels=["a", "b"], values=[1.0, 2.0])],
    )
    assert rows_from_reading(r, "bar-grouped") is None


# --------------------------------------------------------------------------
# The whole thing
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_redraw_without_data_says_so_and_still_draws(tmp_path: Path) -> None:
    out = tmp_path / "redrawn.svg"
    result = redraw(PNG, out=out, client=client_for(reading()))

    assert result.kind == "bar"
    assert result.data_origin == "demo"
    assert result.output.exists()
    assert any("sample data" in w for w in result.warnings)
    # The caption belongs on the figure, not only in the return value: the
    # SVG outlives this call and will be looked at by someone else.
    assert "Sample data" in out.read_text(encoding="utf-8")


@pytest.mark.slow
def test_redraw_with_your_data_makes_no_provenance_claim(tmp_path: Path) -> None:
    out = tmp_path / "real.svg"
    rows = [{"region": "North", "value": 61}, {"region": "South", "value": 39}]
    result = redraw(PNG, out=out, data=rows, client=client_for(reading()))

    assert result.data_origin == "your-data"
    assert result.warnings == []
    svg = out.read_text(encoding="utf-8")
    assert "Sample data" not in svg and "read off" not in svg


@pytest.mark.slow
def test_readable_values_are_marked_approximate_on_the_figure(tmp_path: Path) -> None:
    out = tmp_path / "read.svg"
    result = redraw(
        PNG,
        out=out,
        client=client_for(
            reading(
                values_are_readable=True,
                series=[ReadSeries(name="Revenue", labels=["N", "S"], values=[61.0, 39.0])],
            )
        ),
    )
    assert result.data_origin == "read-from-image"
    assert any("read off a picture" in w for w in result.warnings)
    assert "approximate" in out.read_text(encoding="utf-8").lower()


@pytest.mark.slow
def test_sample_data_does_not_wear_the_originals_axis_labels(tmp_path: Path) -> None:
    """A y-axis reading 'Tonnes shipped' over four invented regions is a quiet lie.

    The kind's own demo chrome stays -- sample data with the caption it was
    written for is coherent. What must not survive is chrome describing the
    ORIGINAL's columns.
    """
    out = tmp_path / "mock.svg"
    redraw(
        PNG,
        out=out,
        client=client_for(
            reading(
                x_label="Fiscal period",
                y_label="Tonnes shipped",
                subtitle="see appendix table 4",
            )
        ),
    )
    svg = out.read_text(encoding="utf-8")
    assert "Fiscal period" not in svg
    assert "Tonnes shipped" not in svg
    assert "appendix table 4" not in svg
    # The title survives: the mock-up is still about that subject.
    assert "two thirds of revenue" in svg


@pytest.mark.slow
def test_your_data_keeps_the_originals_axis_labels(tmp_path: Path) -> None:
    out = tmp_path / "real2.svg"
    redraw(
        PNG,
        out=out,
        data=[{"region": "Q1", "value": 10}, {"region": "Q2", "value": 20}],
        client=client_for(reading(x_label="Fiscal period", y_label="Tonnes shipped")),
    )
    svg = out.read_text(encoding="utf-8")
    assert "Fiscal period" in svg and "Tonnes shipped" in svg


@pytest.mark.slow
def test_french_caption(tmp_path: Path) -> None:
    out = tmp_path / "fr.svg"
    redraw(PNG, out=out, language="fr", client=client_for(reading()))
    assert "Données d'exemple" in out.read_text(encoding="utf-8")


@pytest.mark.slow
def test_naming_the_kind_overrides_the_model(tmp_path: Path) -> None:
    """--kind narrows the candidate list, so the model cannot answer otherwise."""
    result = redraw(
        PNG, out=tmp_path / "d.svg", kind="donut", client=client_for(reading(kind="donut"))
    )
    assert result.kind == "donut"


def test_unknown_kind_is_rejected_before_the_model_is_called() -> None:
    fake = client_for(reading())
    with pytest.raises(ValueError, match="No registered figure"):
        redraw(PNG, kind="no-such-chart", client=fake)
    assert fake.calls == []


@pytest.mark.slow
def test_changes_are_ordered_worst_first(tmp_path: Path) -> None:
    result = redraw(PNG, out=tmp_path / "c.svg", client=client_for(reading()))
    assert len(result.changes) == 2
    assert "critical" in result.changes[0]
    assert "low" in result.changes[1]


@pytest.mark.slow
def test_low_confidence_is_reported(tmp_path: Path) -> None:
    result = redraw(
        PNG, out=tmp_path / "u.svg", client=client_for(reading(kind_confidence="low"))
    )
    assert any("unsure" in w for w in result.warnings)


@pytest.mark.slow
def test_suggested_title_wins_over_the_original(tmp_path: Path) -> None:
    """A title that states the result beats one that states the contents."""
    out = tmp_path / "t.svg"
    redraw(PNG, out=out, client=client_for(reading()))
    assert "two thirds of revenue" in out.read_text(encoding="utf-8")


@pytest.mark.slow
def test_explicit_title_wins_over_everything(tmp_path: Path) -> None:
    out = tmp_path / "t2.svg"
    redraw(PNG, out=out, title="Mine", client=client_for(reading()))
    assert "Mine" in out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The CLI and HTTP surfaces reach the same function
# --------------------------------------------------------------------------


@pytest.mark.slow
def test_cli_redraw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("click")
    from click.testing import CliRunner

    import sprezzature_figures.studio.assistant.client as client_module
    from sprezzature_figures.cli import main

    monkeypatch.setattr(client_module, "default_client", lambda: client_for(reading()))
    image = tmp_path / "theirs.png"
    image.write_bytes(PNG)
    out = tmp_path / "ours.svg"

    result = CliRunner().invoke(main, ["redraw", str(image), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert "bar ->" in result.output
    assert "data: demo" in result.output
    assert "What it does differently" in result.output
    assert out.exists()


def test_cli_refuses_map_without_data(tmp_path: Path) -> None:
    pytest.importorskip("click")
    from click.testing import CliRunner

    from sprezzature_figures.cli import main

    image = tmp_path / "theirs.png"
    image.write_bytes(PNG)
    result = CliRunner().invoke(main, ["redraw", str(image), "--map", "value=v"])
    assert result.exit_code == 1
    assert "--map only applies with --data" in result.output


@pytest.mark.slow
def test_http_redraw(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import sprezzature_figures.studio.assistant.client as client_module
    from sprezzature_figures.api import app

    monkeypatch.setattr(client_module, "default_client", lambda: client_for(reading()))
    resp = TestClient(app).post(
        "/redraw", json={"image_base64": base64.b64encode(PNG).decode("ascii")}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "bar"
    assert body["data_origin"] == "demo"
    assert body["media_type"] == "image/svg+xml"
    assert body["reading"]["suggested_title"]
    svg = base64.b64decode(body["figure_base64"]).decode("utf-8")
    assert svg.lstrip().startswith("<")


def test_http_rejects_payload_that_is_not_base64() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from sprezzature_figures.api import app

    resp = TestClient(app).post("/redraw", json={"image_base64": "not base64 at all!!"})
    assert resp.status_code == 422
    assert "base64" in resp.text


def test_mcp_publishes_the_redraw_tool() -> None:
    """MCP is derived from the HTTP routes, so the tool exists by construction."""
    pytest.importorskip("fastapi")
    from sprezzature_figures.api import app

    operations = {
        route.operation_id for route in app.routes if getattr(route, "operation_id", None)
    }
    assert "redraw_figure" in operations
