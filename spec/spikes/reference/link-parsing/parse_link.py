"""Spike S2: can the publisher read .url and .webloc files with the stdlib only?

PROVES: configparser reads Windows .url shortcuts; plistlib reads both XML and
binary .webloc (macOS writes binary when a link is dragged from the browser).
PROVES: a scheme whitelist rejects javascript:, data:, file: and relative URLs.
SHORTCUT: no size cap, no logging, errors collapse to None without a reason.
"""
import configparser
import plistlib
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}


def parse_link(filename: str, body: bytes) -> str | None:
    name = filename.casefold()
    url = None
    if name.endswith(".url"):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            parser.read_string(body.decode("utf-8-sig", errors="replace"))
            url = parser.get("InternetShortcut", "URL", fallback=None)
        except configparser.Error:
            return None
    elif name.endswith(".webloc"):
        try:
            url = plistlib.loads(body).get("URL")  # detects XML vs binary itself
        except Exception:  # SHORTCUT: plistlib raises several unrelated types
            return None
    if not isinstance(url, str):
        return None
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES or not parts.netloc:
        return None
    return url


if __name__ == "__main__":
    ok = "https://example.com/book?table=2"
    cases = {
        "windows.url": (f"[InternetShortcut]\r\nURL={ok}\r\n".encode(), ok),
        "bom.url": (("﻿[InternetShortcut]\nURL=" + ok + "\n").encode("utf-8"), ok),
        "xml.webloc": (plistlib.dumps({"URL": ok}, fmt=plistlib.FMT_XML), ok),
        "binary.webloc": (plistlib.dumps({"URL": ok}, fmt=plistlib.FMT_BINARY), ok),
        "js.url": (b"[InternetShortcut]\nURL=javascript:alert(1)\n", None),
        "data.webloc": (plistlib.dumps({"URL": "data:text/html,<b>x</b>"}), None),
        "file.url": (b"[InternetShortcut]\nURL=file:///etc/passwd\n", None),
        "relative.url": (b"[InternetShortcut]\nURL=/book\n", None),
        "nosection.url": (b"URL=https://example.com\n", None),
        "garbage.webloc": (b"\x00\x01not a plist", None),
        "upper.URL": (f"[InternetShortcut]\nURL={ok}\n".encode(), ok),
    }
    failures = 0
    for name, (body, expected) in cases.items():
        got = parse_link(name, body)
        status = "ok " if got == expected else "FAIL"
        failures += got != expected
        print(f"{status} {name:16} -> {got!r}")
    print("all passed" if not failures else f"{failures} failed")
