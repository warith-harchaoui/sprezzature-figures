"""
Tests for the FastAPI HTTP surface (sprezzature_figures.api); FastAPI is
the Python web framework this project's HTTP API is built on.

Rendering tests actually call make_figure() and render real SVGs, so
they're marked @pytest.mark.slow, like the equivalent tests in
test_make_figure.py: excluded from the default fast run, included in CI's
second pass (see README.md's Development section).

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import concurrent.futures

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sprezzature_figures.api import app  # noqa: E402

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_redirects_to_docs() -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/docs"


def test_list_kinds() -> None:
    resp = client.get("/kinds")
    assert resp.status_code == 200
    kinds = resp.json()
    assert isinstance(kinds, list)
    assert len(kinds) >= 80
    assert "treemap" in kinds


def test_list_kinds_filtered_by_status() -> None:
    resp = client.get("/kinds", params={"status": "stable"})
    assert resp.status_code == 200
    kinds = resp.json()
    assert "treemap" in kinds
    # Every kind under the filter must genuinely carry that status (all 126
    # happen to be 'stable' right now, so this can't be a fixed negative
    # example -- verify the filter is real by cross-checking each entry).
    for kind in kinds:
        detail = client.get(f"/kinds/{kind}")
        assert detail.json()["status"] == "stable"


def test_get_kind_definition() -> None:
    resp = client.get("/kinds/treemap")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "treemap"
    role_names = {r["name"] for r in body["required_roles"]}
    assert {"parent", "name", "value"} <= role_names


def test_get_kind_definition_resolves_aliases_and_case() -> None:
    # resolve_kind is case/hyphen/underscore-insensitive; the API must be too.
    resp = client.get("/kinds/TreeMap")
    assert resp.status_code == 200
    assert resp.json()["kind"] == "treemap"


def test_get_kind_definition_unknown_404() -> None:
    resp = client.get("/kinds/not-a-real-kind")
    assert resp.status_code == 404


def test_render_unknown_kind_404() -> None:
    resp = client.post("/render/not-a-real-kind", json={})
    assert resp.status_code == 404


def test_render_broken_kind_422_not_500(monkeypatch: pytest.MonkeyPatch) -> None:
    # All 126 registered kinds are 'stable' now, so there is no naturally
    # broken fixture left to hit this path with -- simulate the dispatcher
    # raising the contract-gap error (AttributeError) a genuinely-legacy kind
    # used to produce, and confirm the API still surfaces it as a client
    # error (422), not an unhandled 500.
    import sprezzature_figures.api as api_module

    def broken_make_figure(kind, data, **kwargs):
        raise AttributeError(f"Registered module for {kind!r} has no callable.")

    monkeypatch.setattr(api_module, "make_figure", broken_make_figure)
    resp = client.post("/render/treemap", json={})
    assert resp.status_code == 422


@pytest.mark.slow
def test_render_treemap_demo_data_svg() -> None:
    resp = client.post("/render/treemap", json={"title": "API test"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in resp.content
    assert b"API test" in resp.content


@pytest.mark.slow
def test_render_with_no_body_at_all() -> None:
    # README's documented curl example sends no -d flag, i.e. no HTTP body
    # whatsoever -- distinct from an explicit `json={}`. Every RenderRequest
    # field is optional, so the body itself must default too.
    resp = client.post("/render/treemap")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"


@pytest.mark.slow
def test_render_bar_custom_data() -> None:
    resp = client.post(
        "/render/bar",
        json={"data": [{"region": "North", "value": 42}, {"region": "South", "value": 17}]},
    )
    assert resp.status_code == 200
    assert b"North" in resp.content
    assert b"South" in resp.content


@pytest.mark.slow
def test_render_invalid_data_422() -> None:
    resp = client.post("/render/treemap", json={"data": [{"wrong_field": 1}]})
    assert resp.status_code == 422
    assert "parent" in resp.json()["detail"]


@pytest.mark.slow
def test_render_scale_changes_png_size() -> None:
    import io

    from PIL import Image

    r1 = client.post("/render/bar", json={"format": "png", "scale": 1.0})
    r2 = client.post("/render/bar", json={"format": "png", "scale": 2.0})
    assert r1.status_code == r2.status_code == 200
    im1 = Image.open(io.BytesIO(r1.content))
    im2 = Image.open(io.BytesIO(r2.content))
    assert im2.size[0] == im1.size[0] * 2


@pytest.mark.slow
def test_render_concurrent_scale_does_not_race() -> None:
    """Regression test for the SPREZZATURE_RENDER_SCALE global-env-var race:
    concurrent /render calls with different `scale` must never leak into
    each other (see api.py's _render_lock docstring)."""
    import io

    from PIL import Image

    def fetch(scale: float) -> tuple[float, tuple[int, int]]:
        r = client.post("/render/bar", json={"format": "png", "scale": scale})
        im = Image.open(io.BytesIO(r.content))
        return scale, im.size

    scales = [1.0, 3.0] * 6
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(fetch, scales))

    sizes_at_1x = {size for scale, size in results if scale == 1.0}
    sizes_at_3x = {size for scale, size in results if scale == 3.0}
    assert len(sizes_at_1x) == 1, f"scale=1.0 produced inconsistent sizes: {sizes_at_1x}"
    assert len(sizes_at_3x) == 1, f"scale=3.0 produced inconsistent sizes: {sizes_at_3x}"
    ((w1, _),) = sizes_at_1x
    ((w3, _),) = sizes_at_3x
    assert w3 == w1 * 3


# ---------------------------------------------------------------------------
# POST /recommend -- the tool that keeps an agent from guessing among 127 kinds
# ---------------------------------------------------------------------------

ROWS = [
    {"region": "North", "value": 42},
    {"region": "South", "value": 28},
    {"region": "East", "value": 19},
    {"region": "West", "value": 11},
]


def test_recommend_ranks_kinds_with_their_bindings() -> None:
    pytest.importorskip("pandas")
    resp = client.post("/recommend", json={"data": ROWS, "goal": "comparison", "limit": 4})
    assert resp.status_code == 200, resp.text
    candidates = resp.json()
    assert 1 <= len(candidates) <= 4
    # Bindings are the point: an agent should not have to work out which of
    # its columns fills which role before calling render_figure.
    top = candidates[0]
    assert top["kind"] in ("bar", "lollipop", "pareto")
    assert set(top["bindings"].values()) <= {"region", "value"}
    assert candidates == sorted(candidates, key=lambda c: -c["score"])


def test_recommend_refuses_empty_data() -> None:
    pytest.importorskip("pandas")
    resp = client.post("/recommend", json={"data": []})
    assert resp.status_code == 422
    assert "at least one row" in resp.text


def test_recommend_limit_is_bounded() -> None:
    resp = client.post("/recommend", json={"data": ROWS, "limit": 0})
    assert resp.status_code == 422


def test_check_render_route_reports_a_dropped_title() -> None:
    """
    The route exists, and it catches the failure that needs a caller's intent.

    `check_render` shipped as a library function only: no CLI, no route, no MCP
    tool. A capability an agent cannot reach is a capability it does not have,
    and this one exists precisely so that an agent without a vision model can
    still refuse to hand back an illegible figure.
    """
    import tempfile
    from pathlib import Path

    from sprezzature_figures import make_figure

    with tempfile.TemporaryDirectory() as tmp:
        svg = make_figure("bar", ROWS, out=str(Path(tmp) / "bar.svg")).read_text(encoding="utf-8")

    clean = client.post("/check_render", json={"svg": svg})
    assert clean.status_code == 200, clean.text
    assert clean.json() == [], "the demo bar chart should pass every rule"

    dropped = client.post(
        "/check_render", json={"svg": svg, "expected_title": "A title nobody rendered"}
    )
    assert dropped.status_code == 200, dropped.text
    assert [f["check"] for f in dropped.json()] == ["title_ignored"]


def test_a_row_missing_a_role_is_the_callers_fault_not_a_server_error() -> None:
    """A malformed payload answers 422, not 500.

    ``make_figure`` reads each row by role name, so a row without one raises
    ``KeyError``. That escaped the handler and FastAPI turned it into a 500:
    the status that tells an agent "the server broke, retry later" when the
    truth is "your rows are wrong, fix them and retry now". A bad *value*
    already answered 422 and an unknown kind 404; only the missing key was
    reported as the server's fault.

    The detail now names the column and the row it is missing from: the
    gap check in ``validate_figure_input`` reaches a key absent from one
    row, which the first-row role check could not see.
    """
    from fastapi.testclient import TestClient

    from sprezzature_figures.api import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/render/line",
        json={"data": [{"month": "Jan", "value": 1}, {"month": "Feb"}], "format": "svg"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "value" in detail, detail
    # The row, so the caller does not have to find it: one row of two.
    assert "1 of 2 rows" in detail, detail
    assert "row 1" in detail, detail


# --- the per-figure option surface -------------------------------------


def test_kind_options_lists_what_the_figure_accepts() -> None:
    resp = client.get("/kinds/sankey/options")
    assert resp.status_code == 200
    options = {option["name"]: option for option in resp.json()}
    # sankey's own vocabulary, which no caller could discover before.
    assert options["volume_unit"]["default"] == "visitors"
    assert options["stage_names"]["type"] == "str_list"
    assert options["theme"]["choices"] == ["corporate", "academic"]
    assert options["title"]["cli_flag"] == "--title"


def test_kind_options_404s_on_an_unknown_kind() -> None:
    assert client.get("/kinds/not-a-chart/options").status_code == 404


def test_every_kind_answers_the_options_route() -> None:
    """All 127, not the ones somebody got to -- the point of deriving it."""
    for kind in client.get("/kinds").json():
        payload = client.get(f"/kinds/{kind}/options").json()
        assert payload, f"{kind} publishes no options"


def test_kind_definition_carries_the_same_options() -> None:
    """One figure, one answer: the detail route and the options route agree."""
    detail = client.get("/kinds/sankey").json()
    listed = {option["name"] for option in client.get("/kinds/sankey/options").json()}
    assert set(detail["options_schema"]) == listed


def test_an_unknown_option_is_refused_rather_than_ignored() -> None:
    """A misspelt option used to be dropped, and the figure came back looking ignored."""
    resp = client.post("/render/bar", json={"options": {"widht": 900}})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "Did you mean 'width'" in detail
    assert "/kinds/bar/options" in detail


def test_an_option_belonging_to_another_figure_is_refused() -> None:
    resp = client.post("/render/rose", json={"options": {"width": 900}})
    assert resp.status_code == 422
    assert "rose has no option" in resp.json()["detail"]


def test_a_bad_option_value_is_a_422_not_a_500() -> None:
    resp = client.post("/render/bar", json={"options": {"theme": "neon"}})
    assert resp.status_code == 422
    assert "corporate, academic" in resp.json()["detail"]


@pytest.mark.slow
def test_options_reach_the_rendered_figure() -> None:
    resp = client.post("/render/bar", json={"options": {"width": 1234, "subtitle": "Q3 figures"}})
    assert resp.status_code == 200
    body = resp.content.decode("utf-8")
    assert 'width="1234"' in body
    assert "Q3 figures" in body


@pytest.mark.slow
def test_a_demo_render_keeps_the_chrome_written_for_it() -> None:
    """Omitting `data` draws the reference figure, headline and all."""
    body = client.post("/render/sankey", json={}).content.decode("utf-8")
    assert "Organic search fills the funnel" in body


@pytest.mark.slow
def test_dark_is_reachable_over_http_too() -> None:
    """`dark` existed on the command line and in the library, and not here."""
    light = client.post("/render/bar", json={}).content
    dark = client.post("/render/bar", json={"dark": True}).content
    assert dark != light


def test_every_api_action_has_a_command_line_twin() -> None:
    """The HTTP surface and the command lines offer the same things.

    Not a naming convention for its own sake: three of these routes
    (`redraw`, `recommend`, `check`) existed only in the Click command
    line, so what you could do depended on which door you came through.
    """
    click = pytest.importorskip("click")  # noqa: F841
    from sprezzature_figures.cli import cli
    from sprezzature_figures.make_figure import _VERBS

    operations = {
        route.operation_id
        for route in app.routes
        if getattr(route, "operation_id", None) is not None
    }
    #: route -> the command that does the same thing. `health` is a
    #: liveness probe for a server that a command line does not have.
    twins = {
        "health": None,
        "list_kinds": "list",
        "get_kind": "describe",
        "list_kind_options": "describe",
        "render_figure": "render",
        "redraw_figure": "redraw",
        "recommend_figures": "recommend",
        "check_render": "check",
    }
    assert operations == set(twins), "a route gained or lost without a command to match"
    commands = set(cli.commands) | set(_VERBS) | {"render"}
    missing = {name for name in twins.values() if name is not None} - commands
    assert missing == set(), f"routes with no command-line twin: {missing}"
