"""
Studio's own interface chrome language -- English/French labels, buttons,
placeholders, and notifications for the Studio UI itself.

Distinct from ``studio.i18n`` (``state.language``), which picks the language
a *rendered figure*'s chrome text (title, axis labels) comes out in, re-
detected from each imported CSV's column names. This module is the other
half of the pair the public gallery already has as a 🇫🇷/🇬🇧 toggle: which
language *Studio's own buttons and labels* are in, a per-session user choice
persisted in the browser (see ``pages/editor.py``'s theme-toggle-adjacent
``ui_language`` toggle), never auto-detected.

A plain Python dict, not the ``locales/i18n.yaml`` convention noted for new
GUI work generally: ~40 short key/value pairs don't need file I/O and a
loader when a module-level dict is exactly as inspectable and lets ruff
catch a malformed entry at import time instead of at render time.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

DEFAULT_UI_LANGUAGE = "en"

_STRINGS: dict[str, dict[str, str]] = {
    # data_panel.py
    "no_data_imported": {
        "en": "No data imported yet.",
        "fr": "Aucune donnée importée pour l'instant.",
    },
    "unsupported_file_type": {
        "en": "Unsupported file type {suffix!r}. Upload a .csv, .tsv, .xlsx, .json, or .jsonl file.",
        "fr": "Type de fichier {suffix!r} non pris en charge. Importez un fichier .csv, .tsv, .xlsx, .json ou .jsonl.",
    },
    "file_no_rows": {
        "en": "The file has no data rows.",
        "fr": "Le fichier ne contient aucune ligne de données.",
    },
    "dataset_summary": {
        "en": "{source}: {rows} rows, {cols} columns",
        "fr": "{source} : {rows} lignes, {cols} colonnes",
    },
    "choose_manually": {"en": "Or choose manually", "fr": "Ou choisir manuellement"},
    "figure_kind_label": {"en": "Figure kind", "fr": "Type de figure"},
    "role_optional_suffix": {"en": " (optional)", "fr": " (optionnel)"},
    "choose_kind_first": {
        "en": "Choose a figure kind first.",
        "fr": "Choisissez d'abord un type de figure.",
    },
    "missing_required_roles": {
        "en": "Missing required roles: {roles}",
        "fr": "Rôles requis manquants : {roles}",
    },
    "create_figure": {"en": "Create figure", "fr": "Créer la figure"},
    "upload_error": {"en": "Error: {error}", "fr": "Erreur : {error}"},
    "upload_loaded": {"en": "Loaded {filename}.", "fr": "{filename} importé."},
    "import_label": {"en": "Import CSV, XLSX, or JSON", "fr": "Importer un CSV, XLSX ou JSON"},
    # property_panel.py
    "style_heading": {"en": "Style", "fr": "Style"},
    "text_size_label": {"en": "Text size", "fr": "Taille du texte"},
    "legend_label": {"en": "Legend", "fr": "Légende"},
    "grid_label": {"en": "Grid", "fr": "Grille"},
    "value_labels_label": {"en": "Value labels", "fr": "Étiquettes de valeur"},
    "font_scale_small": {"en": "Small", "fr": "Petit"},
    "font_scale_normal": {"en": "Normal", "fr": "Normal"},
    "font_scale_large": {"en": "Large", "fr": "Grand"},
    "font_scale_larger": {"en": "Larger", "fr": "Plus grand"},
    "font_scale_huge": {"en": "Huge", "fr": "Très grand"},
    "legend_top": {"en": "top", "fr": "haut"},
    "legend_bottom": {"en": "bottom", "fr": "bas"},
    "legend_left": {"en": "left", "fr": "gauche"},
    "legend_right": {"en": "right", "fr": "droite"},
    "legend_none": {"en": "none", "fr": "aucune"},
    # chat_panel.py
    "ralph_mode_label": {"en": "Ralph mode", "fr": "Mode Ralph"},
    "ralph_mode_manual": {"en": "manual", "fr": "manuel"},
    "ralph_mode_assisted": {"en": "assisted", "fr": "assisté"},
    "ralph_mode_autopilot": {"en": "autopilot", "fr": "automatique"},
    "chat_placeholder": {
        "en": "Ask Ralph to change something...",
        "fr": "Demandez un changement à Ralph…",
    },
    "pending_confirmation": {
        "en": "Ralph wants to apply {n} operation(s) that change what the data shows. Confirm to proceed:",
        "fr": "Ralph veut appliquer {n} opération(s) qui changent ce que montrent les données. Confirmez pour continuer :",
    },
    "no_reason_given": {"en": "no reason given", "fr": "aucune raison donnée"},
    "accept": {"en": "Accept", "fr": "Accepter"},
    "cancel": {"en": "Cancel", "fr": "Annuler"},
    "ralph_working": {"en": "Ralph is working...", "fr": "Ralph travaille…"},
    "send": {"en": "Send", "fr": "Envoyer"},
    "create_figure_first": {"en": "Create a figure first.", "fr": "Créez d'abord une figure."},
    # history_panel.py
    "undo_tooltip": {"en": "Undo", "fr": "Annuler"},
    "redo_tooltip": {"en": "Redo", "fr": "Rétablir"},
    "no_versions_yet": {"en": "No versions yet", "fr": "Aucune version pour l'instant"},
    "version_of": {"en": "Version {n} of {total}", "fr": "Version {n} sur {total}"},
    "export_zip": {"en": "Export .zip", "fr": "Exporter .zip"},
    # figure_canvas.py
    "no_render_yet": {
        "en": "No render yet. Import data and create a figure.",
        "fr": "Aucun rendu pour l'instant. Importez des données et créez une figure.",
    },
    # engine_status.py
    "engine_models": {
        "en": "text: {text} · vision: {vision}",
        "fr": "texte : {text} · vision : {vision}",
    },
    "engine_unavailable": {
        "en": "engine unavailable ({status}) — manual editing still works",
        "fr": "moteur indisponible ({status}) — l'édition manuelle fonctionne toujours",
    },
    # recommendation_cards.py
    "recommended": {"en": "Recommended", "fr": "Recommandé"},
    "uses_bindings": {"en": "Uses {bindings}", "fr": "Utilise {bindings}"},
    "use": {"en": "Use", "fr": "Utiliser"},
    # pages/editor.py
    "render_failed": {"en": "Render failed: {error}", "fr": "Échec du rendu : {error}"},
    "figure_created": {"en": "Figure created.", "fr": "Figure créée."},
    "nothing_to_undo": {"en": "Nothing to undo.", "fr": "Rien à annuler."},
    "reverted_previous": {
        "en": "Reverted to the previous version.",
        "fr": "Revenu à la version précédente.",
    },
    "nothing_to_redo": {"en": "Nothing to redo.", "fr": "Rien à rétablir."},
    "restored_next": {"en": "Restored the next version.", "fr": "Version suivante restaurée."},
    "export_failed": {"en": "Export failed: {error}", "fr": "Échec de l'export : {error}"},
    "exported_to": {"en": "Exported to {path}", "fr": "Exporté vers {path}"},
    "cancelled_pending": {
        "en": "Cancelled the pending change(s).",
        "fr": "Changement(s) en attente annulé(s).",
    },
    "switch_to_dark": {"en": "Switch to dark theme", "fr": "Passer au thème sombre"},
    "switch_to_light": {"en": "Switch to light theme", "fr": "Passer au thème clair"},
}

# The language-toggle button's own aria-label is a special case: unlike every
# other string above (same meaning, two languages), this one names the
# *target* language, and only the entry matching the *current* UI language is
# ever read -- an English UI offers "Switch interface to French", a French
# UI offers "Passer l'interface en anglais" (English UI never needs a French
# reading of its own label, so there is no second, unused meaning to keep in
# sync). Kept as a direct dict rather than forcing it through ``t()``.
UI_LANGUAGE_TOGGLE_LABEL: dict[str, str] = {
    "en": "Switch interface to French",
    "fr": "Passer l'interface en anglais",
}


def t(key: str, lang: str, **kwargs: object) -> str:
    """Look up ``key`` in ``lang`` ("en"/"fr"), falling back to English for an
    unsupported language code, and ``.format(**kwargs)`` the result.

    Raises ``KeyError`` on an unknown key -- a typo here should fail loudly
    at the call site, not silently render a blank label.
    """
    entry = _STRINGS[key]
    template = entry.get(lang, entry["en"])
    return template.format(**kwargs) if kwargs else template
