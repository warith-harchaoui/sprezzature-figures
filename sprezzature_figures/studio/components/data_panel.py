"""
Left-hand data panel (plan §13.1 "Données" pane): import a CSV/XLSX,
show the profile, pick a figure kind, and bind data roles to columns.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from nicegui import events, ui

from sprezzature_figures.catalog import get_figure_definition, list_kinds
from sprezzature_figures.core.figure_plan import ColumnBinding, FigurePlan
from sprezzature_figures.studio.components.recommendation_cards import build_recommendation_cards
from sprezzature_figures.studio.ingest import (
    csv_fingerprint,
    excel_fingerprint,
    list_sheets,
    profile_dataframe,
    read_csv,
    read_excel,
    sniff_csv,
    validate_upload_size,
)
from sprezzature_figures.studio.state import SessionState


def _load_upload(state: SessionState, filename: str, content: bytes) -> str | None:
    """Read an uploaded CSV/XLSX (already-read bytes -- see `handle_upload`,
    which is the only caller that has to deal with nicegui's async
    `UploadEventArguments.file.read()`) into state.data/state.dataset_profile.
    Returns an error message, or None on success.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in (".csv", ".tsv", ".xlsx", ".json", ".jsonl", ".ndjson"):
        return f"Unsupported file type {suffix!r} -- upload a .csv, .tsv, .xlsx, .json, or .jsonl file."

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        size_issues = validate_upload_size(tmp_path)
        if size_issues:
            return size_issues[0].message

        if suffix in (".csv", ".tsv"):
            options = sniff_csv(tmp_path)
            df = read_csv(tmp_path, options)
            fingerprint = csv_fingerprint(tmp_path)
            sheet_name = None
        elif suffix in (".json", ".jsonl", ".ndjson"):
            # Reuse the CLI's dependency-light loader so the GUI and
            # `make-figure --data` accept exactly the same JSON shapes.
            import pandas as pd

            from sprezzature_figures.data_source import load_records

            try:
                df = pd.DataFrame(load_records(tmp_path))
            except ValueError as exc:
                return str(exc)
            fingerprint = csv_fingerprint(tmp_path)
            sheet_name = None
        else:
            sheet = list_sheets(tmp_path)[0]
            df = read_excel(tmp_path, sheet_name=sheet)
            fingerprint = excel_fingerprint(tmp_path)
            sheet_name = sheet

        if df.empty:
            return "The file has no data rows."

        state.dataset_profile = profile_dataframe(
            df, dataset_id=fingerprint[:12], fingerprint=fingerprint, source_name=filename, sheet_name=sheet_name
        )
        state.data = df.to_dict("records")
        state.source_name = filename
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


def build_data_panel(state: SessionState, *, on_ready: Callable[[FigurePlan], None]) -> None:
    """Render the import + kind + role-binding controls into the current
    NiceGUI context. `on_ready` is called with a freshly built FigurePlan
    once the user confirms a kind and its role bindings.
    """
    status_label = ui.label("No data imported yet.").classes("text-sm text-gray-500")

    @ui.refreshable
    def binding_form() -> None:
        if state.dataset_profile is None:
            return
        columns = [c.name for c in state.dataset_profile.columns]
        ui.label(f"{state.source_name}: {state.dataset_profile.row_count} rows, {len(columns)} columns").classes(
            "text-sm font-medium"
        )

        # Deterministic recommendations first (one-click, auto-bound), with the
        # manual kind/role controls below for full control.
        build_recommendation_cards(state, on_select=on_ready)
        ui.label("Or choose manually").classes("text-xs text-gray-500 mt-2")

        stable_kinds = list_kinds(status="stable")
        kind_select = ui.select(
            stable_kinds, label="Figure kind", value=stable_kinds[0] if stable_kinds else None
        ).classes("w-full")

        role_selects: dict[str, ui.select] = {}
        role_container = ui.column().classes("w-full gap-1")

        @ui.refreshable
        def render_roles() -> None:
            role_selects.clear()
            role_container.clear()
            if not kind_select.value:
                return
            definition = get_figure_definition(kind_select.value)
            with role_container:
                for role in [*definition.required_roles, *definition.optional_roles]:
                    label = f"{role.label}{'' if role.required else ' (optional)'}"
                    role_selects[role.name] = ui.select(columns, label=label, value=None).classes("w-full")

        kind_select.on_value_change(lambda _: render_roles.refresh())
        with role_container:
            render_roles()

        def confirm() -> None:
            if not kind_select.value:
                ui.notify("Choose a figure kind first.", type="warning")
                return
            definition = get_figure_definition(kind_select.value)
            bindings: dict[str, ColumnBinding] = {}
            missing = []
            for role in definition.required_roles:
                col = role_selects[role.name].value
                if not col:
                    missing.append(role.label)
                    continue
                bindings[role.name] = ColumnBinding(columns=[col])
            for role in definition.optional_roles:
                col = role_selects[role.name].value
                if col:
                    bindings[role.name] = ColumnBinding(columns=[col])
            if missing:
                ui.notify(f"Missing required roles: {', '.join(missing)}", type="warning")
                return
            plan = FigurePlan(figure_kind=kind_select.value, bindings=bindings)
            on_ready(plan)

        ui.button("Create figure", on_click=confirm).props("color=primary").classes("mt-2")

    async def handle_upload(e: events.UploadEventArguments) -> None:
        content = await e.file.read()
        error = _load_upload(state, e.file.name, content)
        if error:
            status_label.text = f"Error: {error}"
            status_label.classes(replace="text-sm text-red-600")
            ui.notify(error, type="negative")
            return
        status_label.text = "Data loaded."
        status_label.classes(replace="text-sm text-green-600")
        binding_form.refresh()

    ui.upload(on_upload=handle_upload, auto_upload=True, label="Import CSV, XLSX, or JSON").props(
        'accept=".csv,.tsv,.xlsx,.json,.jsonl"'
    ).classes("w-full")
    binding_form()
