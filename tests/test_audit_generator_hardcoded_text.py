"""Tests for scripts/audit_generator_hardcoded_text.py — the generator-source
auditor born from the real make_columnrange.py bug (hardcoded "Temperature
(°C)" / "City" axis chrome with no parameter to override it).

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_generator_hardcoded_text as audit  # noqa: E402


def _write(tmp_path: Path, source: str) -> Path:
    p = tmp_path / "make_widget.py"
    p.write_text(textwrap.dedent(source), encoding="utf-8")
    return p


def test_hardcoded_axis_title_flagged_as_warning(tmp_path: Path) -> None:
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            parts = []
            parts.append(f'<text x="18">Temperature (°C)</text>')
            return "\\n".join(parts)
        ''')
    findings = audit.audit_source(src)
    warnings = [f for f in findings if f["severity"] == "warning"]
    assert len(warnings) == 1
    assert warnings[0]["rule"] == "unparameterized-chrome-text"
    assert "Temperature" in warnings[0]["message"]


def test_parameterized_text_not_flagged(tmp_path: Path) -> None:
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget", y_axis_title="Value"):
            parts = []
            parts.append(f'<text x="18">{y_axis_title}</text>')
            parts.append(f'<text x="40">{title}</text>')
            return "\\n".join(parts)
        ''')
    assert audit.audit_source(src) == []


def test_computed_value_with_hardcoded_unit_suffix_flagged(tmp_path: Path) -> None:
    """Reproduces the tooltip half of the real bug: `f"{low:.0f}°C"` mixes a
    computed value with a hardcoded unit that had no parameter either."""
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            parts = []
            low = 10
            parts.append(f'<text x="18">{low:.0f} degrees Celsius</text>')
            return "\\n".join(parts)
        ''')
    findings = audit.audit_source(src)
    assert any("degrees Celsius" in f["message"] for f in findings)


def test_safe_unit_residue_not_flagged(tmp_path: Path) -> None:
    """A single '%' or '€' left over after stripping the computed value is
    not chart chrome — it's inseparable formatting, not an override target."""
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            parts = []
            val = 10
            parts.append(f'<text x="18">{val:.0f}%</text>')
            return "\\n".join(parts)
        ''')
    assert audit.audit_source(src) == []


def test_long_narrative_text_flagged_as_info_not_warning(tmp_path: Path) -> None:
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            parts = []
            parts.append(f'<text x="18">Winter does most of the waiting here</text>')
            return "\\n".join(parts)
        ''')
    findings = audit.audit_source(src)
    assert len(findings) == 1
    assert findings[0]["severity"] == "info"
    assert findings[0]["rule"] == "unparameterized-narrative-text"


def test_non_generator_file_skipped(tmp_path: Path) -> None:
    p = tmp_path / "helpers.py"
    p.write_text('X = f"<text>Not a generator</text>"', encoding="utf-8")
    assert audit.audit_source(p) == []


def test_real_fixed_columnrange_generator_is_clean() -> None:
    """Regression guard for the actual bug this tool was built for: the fixed
    make_columnrange.py must report zero warnings."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "make_columnrange.py"
    findings = audit.audit_source(path)
    warnings = [f for f in findings if f["severity"] == "warning"]
    assert warnings == [], warnings


def test_cli_exit_code_strict_vs_default(tmp_path: Path, capsys) -> None:
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            return f'<text x="18">Value</text>'
        ''')
    assert audit.main([str(src)]) == 0  # warnings alone don't fail without --strict
    assert audit.main([str(src), "--strict"]) == 1
    assert audit.main([str(src), "--strict", "--ignore", "unparameterized-chrome-text"]) == 0


def test_json_output_shape(tmp_path: Path, capsys) -> None:
    src = _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            return f'<text x="18">Value</text>'
        ''')
    audit.main([str(src), "--json"])
    out = capsys.readouterr().out
    assert '"unparameterized-chrome-text"' in out
    assert '"warnings": 1' in out


def test_directory_scan_only_matches_make_prefixed_files(tmp_path: Path) -> None:
    _write(tmp_path, '''
        def build_svg(data=None, title="Widget"):
            return f'<text x="18">Value</text>'
        ''')
    (tmp_path / "_helpers.py").write_text('f"<text>Ignored (not make_*)</text>"', encoding="utf-8")
    files = audit.iter_files([str(tmp_path)])
    assert [f.name for f in files] == ["make_widget.py"]
