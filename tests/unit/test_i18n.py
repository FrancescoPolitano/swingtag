"""Unit tests for i18n.py."""
from datetime import datetime, timezone

from swingtag import i18n

FR14 = {
    "updated": ("Updated on", "Aggiornato il"),
    "empty": ("Nothing is available here yet.", "Qui non c'è ancora nulla."),
    "not_found_title": ("Page not available", "Pagina non disponibile"),
    "not_found_body": (
        "This code does not match any published page. Check that you scanned the whole code.",
        "Questo codice non corrisponde a nessuna pagina pubblicata. Verifica di aver inquadrato il codice per intero.",
    ),
    "kind_document": ("Document", "Documento"),
    "kind_image": ("Image", "Immagine"),
    "kind_audio": ("Audio", "Audio"),
    "kind_video": ("Video", "Video"),
    "kind_link": ("Link", "Link"),
}
MOMENT = datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc)


def test_every_key_every_locale():
    for key, (en, it) in FR14.items():
        assert i18n.STRINGS["en"][key] == en
        assert i18n.STRINGS["it"][key] == it
    assert set(i18n.STRINGS["en"]) == set(FR14) == set(i18n.STRINGS["it"])


def test_date_it():
    assert i18n.format_date(MOMENT, "it", "Europe/Rome") == "25/09/2026 14:30"


def test_date_en():
    assert i18n.format_date(MOMENT, "en", "Europe/Rome") == "25 Sep 2026, 14:30"


def test_naive_datetime_is_utc():
    """Deferred minor M6."""
    assert i18n.format_date(datetime(2026, 9, 25, 12, 30), "it", "Europe/Rome") == "25/09/2026 14:30"
