"""Fixed wording of the pages in each locale, and date formatting."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "updated": "Updated on",
        "empty": "Nothing is available here yet.",
        "not_found_title": "Page not available",
        "not_found_body": "This code does not match any published page. "
        "Check that you scanned the whole code.",
        "kind_document": "Document",
        "kind_image": "Image",
        "kind_audio": "Audio",
        "kind_video": "Video",
        "kind_link": "Link",
    },
    "it": {
        "updated": "Aggiornato il",
        "empty": "Qui non c'è ancora nulla.",
        "not_found_title": "Pagina non disponibile",
        "not_found_body": "Questo codice non corrisponde a nessuna pagina pubblicata. "
        "Verifica di aver inquadrato il codice per intero.",
        "kind_document": "Documento",
        "kind_image": "Immagine",
        "kind_audio": "Audio",
        "kind_video": "Video",
        "kind_link": "Link",
    },
}

# English month abbreviations spelled out: the Lambda runtime has only the C locale,
# so strftime("%b") cannot be trusted to follow the page locale.
_MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_date(moment: datetime, locale: str, timezone: str) -> str:
    """`25/09/2026 14:30` for it, `25 Sep 2026, 14:30` for en (and any other locale)."""
    if moment.tzinfo is None:  # naive values are UTC, never the host's clock
        moment = moment.replace(tzinfo=dt_timezone.utc)
    local = moment.astimezone(ZoneInfo(timezone))
    if locale == "it":
        return local.strftime("%d/%m/%Y %H:%M")
    return f"{local.day} {_MONTHS_EN[local.month - 1]} {local.year}, {local:%H:%M}"
