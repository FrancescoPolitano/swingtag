"""Vector QR code of an item URL.

Level Q (about 25 % of modules recoverable): the code lives on a label exposed
to handling, sun and dirt. Vector output because the print size is unknown.
"""

from __future__ import annotations

import io

import qrcode
from qrcode.image.svg import SvgPathImage


def _code(url: str) -> qrcode.QRCode:
    code = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=2,
        image_factory=SvgPathImage,
    )
    code.add_data(url)
    code.make(fit=True)
    return code


def qr_svg(url: str) -> bytes:
    buffer = io.BytesIO()
    _code(url).make_image().save(buffer)
    return buffer.getvalue()
