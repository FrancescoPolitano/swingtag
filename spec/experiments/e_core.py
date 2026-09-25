"""Local experiments on the pure-Python assumptions of the spec.

Each function validates one technical assumption (T-xx in spec/ASSUMPTIONS.md)
and prints PASS/FAIL with the measured evidence. Run: python3 e_core.py
The code here is experimental: it re-implements the rule under test in the
smallest form, it is not the product code.
"""
import collections
import hashlib
import hmac
import os
import re
import secrets
import sys
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
results = []


def check(tid, ok, evidence):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {tid}: {evidence}")


def token_for(collection, label, secret):
    m = f"{unicodedata.normalize('NFC', collection)}\x00{unicodedata.normalize('NFC', label)}".encode()
    d = hmac.new(secret.encode(), m, hashlib.sha256).digest()
    return "".join(ALPHABET[b % 32] for b in d[:12])


def t01_nfc():
    nfd = unicodedata.normalize("NFD", "Menù Caffè")
    nfc = unicodedata.normalize("NFC", "Menù Caffè")
    check("T-01", nfd != nfc and unicodedata.normalize("NFC", nfd) == nfc,
          f"NFD len {len(nfd)} vs NFC len {len(nfc)}; equal after NFC")


def t02_uniform():
    # 256 % 32 == 0, so byte % 32 is exactly uniform; measure it on 2M samples too.
    counts = collections.Counter(b % 32 for b in os.urandom(2_000_000))
    exp = 2_000_000 / 32
    chi2 = sum((c - exp) ** 2 / exp for c in counts.values())
    # chi-square critical value, 31 dof, p=0.001: 61.1
    check("T-02", 256 % 32 == 0 and chi2 < 61.1 and len(ALPHABET) == 32 and not set("lo01") & set(ALPHABET),
          f"256%32=0, chi2={chi2:.1f} (<61.1), alphabet 32 symbols without l,o,0,1, 12x5=60 bits")


def t03_derivation():
    s1, s2 = secrets.token_hex(32), secrets.token_hex(32)
    a = token_for("Vivaio", "Olivo", s1)
    same = all(token_for("Vivaio", "Olivo", s1) == a for _ in range(100))
    nfd_same = token_for(unicodedata.normalize("NFD", "Vivaio Città"), "Olivo", s1) == token_for("Vivaio Città", "Olivo", s1)
    other_key = token_for("Vivaio", "Olivo", s2) != a
    boundary = token_for("ab", "c", s1) != token_for("a", "bc", s1)
    fmt = re.fullmatch(f"[{ALPHABET}]{{12}}", a) is not None
    check("T-03", same and nfd_same and other_key and boundary and fmt,
          f"deterministic x100, NFC-insensitive, key-sensitive, separator-safe, format ok ({a})")


ORDER = re.compile(r"^(\d{1,6})\s*(?:[.)\-]\s*|\s+)(.+)$")


def t04_order():
    cases = {"10 Lunch": (10, "Lunch"), "10. Lunch": (10, "Lunch"), "10 - Lunch": (10, "Lunch"),
             "10) Lunch": (10, "Lunch"), "10": None, "Table 3 north": None, "1234567 X": None}
    ok = True
    for name, exp in cases.items():
        m = ORDER.match(name)
        got = (int(m.group(1)), m.group(2)) if m else None
        ok &= got == exp
    check("T-04", ok, f"{len(cases)} cases: four separators, digits-only, inner number, 7 digits")


# Letters with no ASCII decomposition: NFKD alone drops them ("Straße" -> "strae").
EXTRA = str.maketrans({"ß": "ss", "ẞ": "SS", "Æ": "AE", "æ": "ae", "Œ": "OE", "œ": "oe",
                       "Ø": "O", "ø": "o", "Đ": "D", "đ": "d", "Ł": "L", "ł": "l", "Þ": "Th", "þ": "th"})


def slug_nfkd_only(value, fallback):
    a = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", a).strip("-") or fallback


def slug(value, fallback):
    a = unicodedata.normalize("NFKD", value.translate(EXTRA)).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", a).strip("-") or fallback


def t05_slug():
    cases = {"Manutenzione perché": "manutenzione-perche", "Crème brûlée": "creme-brulee",
             "★★★": "entry", "Straße": "strasse", "Œuvre": "oeuvre", "Ølstue": "olstue", "Łódź": "lodz", "Care/1": "care-1", "Care 1": "care-1"}
    got = {k: slug(k, "entry") for k in cases}
    ok = got == cases and slug_nfkd_only("Straße", "entry") == "strae"
    check("T-05", ok, f"NFKD alone drops letters (Straße->strae); with the EXTRA table: {got}")


def t17_dates():
    # Month names must not depend on the OS locale: the runtime has only C/POSIX.
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    dt = datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc)
    rome = dt.astimezone(ZoneInfo("Europe/Rome"))
    it = rome.strftime("%d/%m/%Y %H:%M")
    en = f"{rome.day} {months[rome.month - 1]} {rome.year}, {rome:%H:%M}"
    try:
        ZoneInfo("Mars/Olympus")
        bad = False
    except Exception:
        bad = True
    check("T-17", it == "25/09/2026 14:30" and en == "25 Sep 2026, 14:30" and bad,
          f"it='{it}' en='{en}' invalid tz raises -> fallback path exists (local tzdata; Lambda tzdata is A-xx)")


def t12_qrcode_pure():
    import qrcode  # noqa: F401  (installed from the py3-none-any wheel)
    from qrcode.image.svg import SvgPathImage
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, image_factory=SvgPathImage, border=2)
    url = "https://d1234567890abc.cloudfront.net/3xk9m2p7qhv4"
    code.add_data(url)
    code.make(fit=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out, exist_ok=True)
    import io
    buf = io.BytesIO()
    code.make_image().save(buf)
    open(os.path.join(out, "qr.svg"), "wb").write(buf.getvalue())
    check("T-12", buf.getvalue().startswith(b"<?xml"),
          f"SVG {len(buf.getvalue())} bytes, QR version {code.version} for a cloudfront URL, no native deps")


if __name__ == "__main__":
    for f in (t01_nfc, t02_uniform, t03_derivation, t04_order, t05_slug, t17_dates, t12_qrcode_pure):
        f()
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)
