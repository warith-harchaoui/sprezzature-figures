"""
Studio-only figure language: which of a small set of language-aware
generators (see ``core.rendering._LANGUAGE_AWARE_KINDS``) should render its
chrome text (title, subtitle, axis/legend labels) in French vs English.

Default is French -- Studio's own default, not the library's (``make_figure``
called directly, via the CLI, the API, or MCP always defaults a generator's
`language` param to "en"). Once a CSV is imported, the language of its
*column names* becomes the single language for everything rendered from it,
so one dataset never mixes French axis chrome with an English legend.

Author
------
Warith Harchaoui <warith.harchaoui@gmail.com>
"""

from __future__ import annotations

import re
import unicodedata

from langdetect import DetectorFactory, LangDetectException, detect

# langdetect's Naive-Bayes detector samples random character n-grams when the
# input is ambiguous; without a fixed seed the same column names can flip
# between "fr" and "en" across two imports of the same file.
DetectorFactory.seed = 0

#: Studio's language before any CSV is imported (and its fallback whenever
#: nothing below can decide).
DEFAULT_LANGUAGE = "fr"

_SUPPORTED = {"fr", "en"}

# Common data-column vocabulary, curated by hand: column headers are one or
# two words with almost no grammar, so a statistical detector (langdetect)
# is unreliable on them -- tested on this repo's own demo CSVs, it called
# "region quarter revenue" French. A small bilingual dictionary vote is
# deterministic and correct for the vocabulary spreadsheets/CSVs actually
# use; langdetect is kept only as a last-resort fallback below.
_FR_WORDS = {
    "region", "trimestre", "revenu", "valeur", "nom", "mois", "abonnes",
    "abonne", "pays", "ventes", "vente", "prix", "categorie", "montant",
    "nombre", "identifiant", "equipe", "departement", "produit", "quantite",
    "annee", "semaine", "jour", "client", "employe", "cout", "benefice",
    "depense", "croissance", "effectif", "effectifs", "chiffre", "affaires",
    "societe", "date", "titre", "description", "statut", "type", "groupe",
    "parent",
}
_EN_WORDS = {
    "quarter", "revenue", "value", "name", "month", "subscribers",
    "subscriber", "country", "sales", "price", "category", "amount",
    "count", "id", "team", "department", "product", "quantity", "year",
    "week", "day", "customer", "employee", "cost", "profit", "budget",
    "spend", "growth", "region", "title", "status", "group", "parent",
    "type", "date",
}

_FR_DIACRITICS = re.compile(r"[éèêëàâäùûüôöîïç]", re.IGNORECASE)
_TOKEN_SPLIT = re.compile(r"[^a-zà-ÿ]+")


def _strip_accents(token: str) -> str:
    normalized = unicodedata.normalize("NFKD", token)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def detect_language(column_names: list[str]) -> str:
    """Return ``"fr"`` or ``"en"`` for a dataset's column names.

    Parameters
    ----------
    column_names : list of str
        The imported CSV's header row, e.g. ``["region", "quarter",
        "revenue"]`` or ``["mois", "abonnes"]``.

    Returns
    -------
    str
        ``"fr"`` or ``"en"``, decided by (in order): the presence of a
        French diacritic anywhere in the headers, a majority vote against
        :data:`_FR_WORDS` / :data:`_EN_WORDS`, then a ``langdetect`` guess on
        the joined text as a last resort. Falls back to
        :data:`DEFAULT_LANGUAGE` when `column_names` is empty or nothing
        above can decide.
    """
    text = " ".join(str(c).strip() for c in column_names if str(c).strip())
    if not text:
        return DEFAULT_LANGUAGE

    if _FR_DIACRITICS.search(text):
        return "fr"

    fr_votes = en_votes = 0
    for raw_col in column_names:
        for token in _TOKEN_SPLIT.split(_strip_accents(str(raw_col).lower())):
            if not token:
                continue
            in_fr, in_en = token in _FR_WORDS, token in _EN_WORDS
            if in_fr and not in_en:
                fr_votes += 1
            elif in_en and not in_fr:
                en_votes += 1
    if fr_votes or en_votes:
        return "fr" if fr_votes > en_votes else "en"

    try:
        detected = detect(text)
    except LangDetectException:
        return DEFAULT_LANGUAGE
    return detected if detected in _SUPPORTED else DEFAULT_LANGUAGE
