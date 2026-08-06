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


def test_discover_and_dispatcher_reachability() -> None:
    # Discovery finds every make_<kind> script (never make_figure itself)...
    scripts = audit.discover_scripts()
    assert len(scripts) >= 80
    assert all(p.name.startswith("make_") and p.stem != "make_figure" for p in scripts)

    # ...and dispatcher_reachable tells a plain name (treemap) apart from a
    # hyphenated one whose file the underscore-guessing dispatcher can't find.
    hyphenated = audit.SCRIPTS_DIR / "make_connected-scatter.py"
    assert audit.derive_kind(hyphenated) == "connected-scatter"
    assert audit.dispatcher_reachable("connected-scatter", hyphenated) is False
    plain = audit.SCRIPTS_DIR / "make_treemap.py"
    assert audit.dispatcher_reachable(audit.derive_kind(plain), plain) is True


def test_static_audit_is_wellformed_and_never_swallows_errors() -> None:
    entries = audit.run_audit(render=False, timeout=5)
    assert len(entries) == len(audit.discover_scripts())
    for entry in entries:
        assert entry["status"] in _VALID_STATUSES
        assert entry["render_test"] in _VALID_RENDER_STATES
        # An import failure always carries a recorded reason, and no error is
        # ever a blank/non-string, so nothing is silently swallowed.
        if not entry["importable"]:
            assert entry["import_error"]
        for err in entry["errors"]:
            assert isinstance(err, str) and err.strip()


@pytest.mark.parametrize(
    "kind, callable_exists, status",
    [
        # sankey was rewritten to take real data + expose make_sankey (plan §7).
        ("sankey", True, None),
        # difference-chart was promoted to the contract (make_difference_chart,
        # real data threaded through); render=False here so the best this
        # static-only pass can confirm is "experimental", not "stable" (that
        # needs a successful --render, covered by the slow test below).
        ("difference-chart", True, "experimental"),
    ],
)
def test_audit_reflects_each_generator_contract(kind, callable_exists, status) -> None:
    entry = next(e for e in audit.run_audit(render=False, timeout=5) if e["kind"] == kind)
    assert entry["importable"] is True
    assert entry["callable_exists"] is callable_exists
    if kind == "sankey":
        assert entry["demo_data_exists"] is True
    if status is not None:
        assert entry["status"] == status


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
