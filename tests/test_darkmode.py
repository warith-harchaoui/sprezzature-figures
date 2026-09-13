"""Dark mode: transparent background + lightened chrome, data colours intact."""
from __future__ import annotations

import tempfile
from pathlib import Path

from sprezzature_figures import make_figure, to_dark


def test_to_dark_drops_background_and_lightens_chrome():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400">'
           '<rect width="640" height="400" fill="#FFFFFF"/>'
           '<text fill="#1D1D1F">t</text><text fill="#6E6E73">s</text>'
           '<line stroke="#E5E5EA"/></svg>')
    out = to_dark(svg)
    assert '<rect width="640" height="400" fill="#FFFFFF"/>' not in out  # bg dropped
    assert "#1D1D1F" not in out and "#F5F5F7" in out
    assert "#6E6E73" not in out and "#98989D" in out
    assert "#E5E5EA" not in out and "#3A3A3C" in out


def test_to_dark_preserves_data_colours_and_useful_white():
    svg = ('<svg width="100" height="100"><rect width="100" height="100" fill="#FFFFFF"/>'
           '<rect x="10" y="10" width="20" height="50" fill="#007AFF"/>'
           '<text fill="#FFFFFF">42</text></svg>')
    out = to_dark(svg)
    assert 'fill="#007AFF"' in out                    # data colour kept
    assert 'fill="#FFFFFF">42</text>' in out          # white-on-bar kept
    assert '<rect width="100" height="100" fill="#FFFFFF"/>' not in out


def test_make_figure_dark_option_produces_dark_svg():
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "bar.svg"
        make_figure("bar", [{"region": "A", "value": 3}, {"region": "B", "value": 5}],
                    out=str(p), dark=True)
        svg = p.read_text(encoding="utf-8")
    assert "#1D1D1F" not in svg          # no dark ink left
    assert "#F5F5F7" in svg              # light ink present
    # the full-canvas white background rect is gone
    import re
    m = re.search(r'width="(\d+)"\s+height="(\d+)"', svg)
    if m:
        w, h = m.group(1), m.group(2)
        assert f'<rect width="{w}" height="{h}" fill="#FFFFFF"/>' not in svg


def test_make_figure_default_is_light_unchanged():
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "bar.svg"
        make_figure("bar", [{"region": "A", "value": 3}], out=str(p))
        svg = p.read_text(encoding="utf-8")
    assert "#1D1D1F" in svg  # light default keeps dark ink
