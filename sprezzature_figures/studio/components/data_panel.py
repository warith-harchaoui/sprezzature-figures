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
from sprezzature_figures.studio.i18n import detect_language
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
from sprezzature_figures.studio.ui_strings import t


def _load_upload(state: SessionState, filename: str, content: bytes) -> str | None:
    """Read an uploaded CSV/XLSX (already-read bytes -- see `handle_upload`,
    which is the only caller that has to deal with nicegui's async
    `UploadEventArguments.file.read()`) into state.data/state.dataset_profile.
    Returns an error message, or None on success.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in (".csv", ".tsv", ".xlsx", ".json", ".jsonl", ".ndjson"):
        return t("unsupported_file_type", state.ui_language, suffix=suffix)

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
            return t("file_no_rows", state.ui_language)

        state.dataset_profile = profile_dataframe(
            df,
            dataset_id=fingerprint[:12],
            fingerprint=fingerprint,
            source_name=filename,
            sheet_name=sheet_name,
        )
        state.data = df.to_dict("records")
        state.source_name = filename
        # This CSV's column names become the one chrome language every
        # figure built from it renders in (see studio/i18n.py) -- re-detected
        # per import so a second file in the same session can switch it.
        state.language = detect_language(list(df.columns))
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


def build_data_panel(
    state: SessionState, *, on_ready: Callable[[FigurePlan], None]
) -> Callable[[], None]:
    """Render the import + kind + role-binding controls into the current
    NiceGUI context. `on_ready` is called with a freshly built FigurePlan
    once the user confirms a kind and its role bindings. Returns a
    `refresh_language()` the editor's UI-language toggle calls.
    """
    status_label = ui.label(t("no_data_imported", state.ui_language)).classes(
        "text-sm text-gray-500"
    )
    # What status_label should say, tracked separately from its rendered text
    # so a language toggle can re-format the *same* status (an error's text,
    # a loaded filename) instead of only ever falling back to "no data yet".
    status: dict[str, str | None] = {"kind": "none", "text": None}

    def paint_status() -> None:
        lang = state.ui_language
        if status["kind"] == "error":
            status_label.text = t("upload_error", lang, error=status["text"])
            status_label.classes(replace="text-sm text-red-600")
        elif status["kind"] == "loaded":
            status_label.text = t("upload_loaded", lang, filename=status["text"])
            status_label.classes(replace="text-sm text-green-600")
        else:
            status_label.text = t("no_data_imported", lang)
            status_label.classes(replace="text-sm text-gray-500")

    @ui.refreshable
    def binding_form() -> None:
        if state.dataset_profile is None:
            return
        lang = state.ui_language
        columns = [c.name for c in state.dataset_profile.columns]
        ui.label(
            t(
                "dataset_summary",
                lang,
                source=state.source_name,
                rows=state.dataset_profile.row_count,
                cols=len(columns),
            )
        ).classes("text-sm font-medium")

        # Deterministic recommendations first (one-click, auto-bound), with the
        # manual kind/role controls below for full control.
        build_recommendation_cards(state, on_select=on_ready)
        ui.label(t("choose_manually", lang)).classes("text-xs text-gray-500 mt-2")

        stable_kinds = list_kinds(status="stable")
        kind_select = ui.select(
            stable_kinds,
            label=t("figure_kind_label", lang),
            value=stable_kinds[0] if stable_kinds else None,
        ).classes("w-full")

        role_selects: dict[str, ui.select] = {}
        role_container = ui.column().classes("w-full gap-1")

        # Build elements directly (no nested `with role_container:` and no
        # manual `role_container.clear()`): `@ui.refreshable` already wraps
        # this call in its own tracked container and clears *that* container
        # before each `.refresh()`. The previous version re-entered
        # `with role_container:` and cleared `role_container` itself from
        # inside the function -- on the very first call that deleted the
        # refreshable's own freshly-created container as a side effect
        # (it was a child of role_container), silently dropping it from
        # `render_roles.targets` on the next `.refresh()`'s `prune()`. Every
        # later kind switch then called a `.refresh()` with zero live
        # targets: no exception, no log line, nothing -- the dropdown label
        # changed but the role fields underneath never did. Letting the
        # decorator own its container (elements just parented to whatever
        # `role_container` wraps) fixes both the crash-on-switch bug this
        # comment used to describe and the visible-refresh gap it left open.
        @ui.refreshable
        def render_roles(kind: str | None) -> None:
            role_selects.clear()
            if not kind:
                return
            definition = get_figure_definition(kind)
            for role in [*definition.required_roles, *definition.optional_roles]:
                label = f"{role.label}{'' if role.required else t('role_optional_suffix', lang)}"
                role_selects[role.name] = ui.select(columns, label=label, value=None).classes(
                    "w-full"
                )

        # Pass the new value straight from the change event instead of having
        # render_roles() re-read kind_select.value itself: relying on the
        # select's own .value inside the refreshable left role_selects built
        # for the *previous* kind after a switch, so confirm() below could
        # read stale role names.
        kind_select.on_value_change(lambda e: render_roles.refresh(e.value))
        with role_container:
            render_roles(kind_select.value)

        def confirm() -> None:
            if not kind_select.value:
                ui.notify(t("choose_kind_first", lang), type="warning")
                return
            definition = get_figure_definition(kind_select.value)
            bindings: dict[str, ColumnBinding] = {}
            missing = []
            for role in [*definition.required_roles, *definition.optional_roles]:
                select = role_selects.get(role.name)
                col = select.value if select else None
                if not col:
                    if role.required:
                        missing.append(role.label)
                    continue
                bindings[role.name] = ColumnBinding(columns=[col])
            if missing:
                ui.notify(
                    t("missing_required_roles", lang, roles=", ".join(missing)), type="warning"
                )
                return
            plan = FigurePlan(figure_kind=kind_select.value, bindings=bindings)
            on_ready(plan)

        ui.button(t("create_figure", lang), on_click=confirm).props("color=primary").classes("mt-2")

    async def handle_upload(e: events.UploadEventArguments) -> None:
        content = await e.file.read()
        error = _load_upload(state, e.file.name, content)
        if error:
            status["kind"], status["text"] = "error", error
            paint_status()
            ui.notify(error, type="negative")
            uploader.reset()
            return
        status["kind"], status["text"] = "loaded", e.file.name
        paint_status()
        binding_form.refresh()
        # Clear the uploader's file row (and its raw "98.0B / 100.00%" progress
        # line) once the data is in state: the row count below is the durable
        # confirmation, and a fresh dropzone keeps re-importing one click away.
        uploader.reset()

    uploader = (
        ui.upload(
            on_upload=handle_upload, auto_upload=True, label=t("import_label", state.ui_language)
        )
        .props('accept=".csv,.tsv,.xlsx,.json,.jsonl"')
        .classes("w-full")
    )
    binding_form()

    def refresh_language() -> None:
        paint_status()
        uploader.props(f"label='{t('import_label', state.ui_language)}'")
        binding_form.refresh()

    return refresh_language
