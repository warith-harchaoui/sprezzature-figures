"""
Tests for tools/audit_generators.py.

These do not require every figure to be stable — they require the audit
itself to be runnable and to give every discovered script an explicit,
well-formed verdict. Slow (renders every contract-complete generator) is
marked and excluded from the default run.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools import audit_generators as audit  # noqa: E402

_VALID_STATUSES = {"stable", "experimental", "legacy", "unavailable"}
_VALID_RENDER_STATES = {"not_run", "passed", "failed", "skipped"}


def test_discover_scripts_finds_every_generator() -> None:
    scripts = audit.discover_scripts()
    assert len(scripts) >= 80
    assert all(p.name.startswith("make_") for p in scripts)
    assert all(p.stem != "make_figure" for p in scripts)


def test_dispatcher_reachable_detects_hyphen_mismatch() -> None:
    path = audit.SCRIPTS_DIR / "make_connected-scatter.py"
    assert path.exists(), "fixture script missing"
    kind = audit.derive_kind(path)
    assert kind == "connected-scatter"
    assert audit.dispatcher_reachable(kind, path) is False


def test_dispatcher_reachable_true_for_plain_name() -> None:
    path = audit.SCRIPTS_DIR / "make_treemap.py"
    kind = audit.derive_kind(path)
    assert audit.dispatcher_reachable(kind, path) is True


def test_static_audit_gives_every_script_an_explicit_status() -> None:
    entries = audit.run_audit(render=False, timeout=5)
    assert len(entries) == len(audit.discover_scripts())
    for entry in entries:
        assert entry["status"] in _VALID_STATUSES
        assert entry["render_test"] in _VALID_RENDER_STATES
        # Import failures must always carry a recorded reason, never a
        # silently-swallowed exception.
        if not entry["importable"]:
            assert entry["import_error"]


def test_sankey_currently_fails_the_make_contract() -> None:
    """Documents the known gap: sankey exposes build_svg()/main(), not make_sankey()."""
    entries = audit.run_audit(render=False, timeout=5)
    sankey = next(e for e in entries if e["kind"] == "sankey")
    assert sankey["importable"] is True
    assert sankey["callable_exists"] is False
    assert sankey["status"] == "legacy"


def test_import_errors_are_never_swallowed_without_a_message() -> None:
    entries = audit.run_audit(render=False, timeout=5)
    for entry in entries:
        for err in entry["errors"]:
            assert isinstance(err, str) and err.strip()


@pytest.mark.slow
def test_render_audit_marks_contract_complete_scripts_stable_or_experimental() -> None:
    entries = audit.run_audit(render=True, timeout=30)
    contract_complete = [
        e
        for e in entries
        if e["callable_exists"] and e["demo_data_exists"] and e["accepts_data"] and e["accepts_out"]
    ]
    assert contract_complete, "expected at least one contract-complete generator"
    for entry in contract_complete:
        assert entry["status"] in {"stable", "experimental"}
        assert entry["render_test"] in {"passed", "failed"}
