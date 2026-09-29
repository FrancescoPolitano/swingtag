"""Unit tests for qr.py."""
import cv2
import numpy as np
import qrcode

from swingtag import qr

URL = "https://d1234567890abc.cloudfront.net/3xk9m2p7qhv4"


def test_qr_decodes():
    svg = qr.qr_svg(URL)
    assert svg.startswith(b"<?xml") and b"<path" in svg
    matrix = np.array(qr._code(URL).get_matrix(), dtype=np.uint8)  # includes the border
    image = np.where(matrix == 1, 0, 255).astype(np.uint8)
    image = cv2.resize(image, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    image = np.pad(image, 40, constant_values=255)  # generous quiet zone for the detector
    data, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    assert data == URL


def test_qr_level_q():
    assert qr._code(URL).error_correction == qrcode.constants.ERROR_CORRECT_Q
