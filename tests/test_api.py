"""
Tests for the FastAPI HTTP surface (sprezzature_figures.api).

Rendering tests actually call make_figure() (they render real SVGs), so
they're marked @pytest.mark.slow like the equivalent tests in
test_make_figure.py -- excluded from the default fast run, included in CI's
second pass (see README.md's Development section).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
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
    # A known-legacy kind must not appear under the stable filter.
    assert "rose" not in kinds


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


def test_render_legacy_kind_422_not_500() -> None:
    # "rose" is a registered-but-legacy kind (no make_<kind> callable yet).
    # The dispatcher's AttributeError must surface as a client error (422),
    # not an unhandled 500 -- the registry already told the caller it was
    # legacy via GET /kinds/rose's "status" field.
    resp = client.post("/render/rose", json={})
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
    (w1, _), = sizes_at_1x
    (w3, _), = sizes_at_3x
    assert w3 == w1 * 3
