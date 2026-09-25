"""T-13: the SVG QR code produced by qrcode 8.2 (level Q) decodes back to the URL.

Input: out/qr-rendered.png, a browser screenshot of out/qr.svg (see e_core.py
t12_qrcode_pure). Decoder: OpenCV QRCodeDetector (experiment-only dependency).
"""
import sys
import cv2

EXPECTED = "https://d1234567890abc.cloudfront.net/3xk9m2p7qhv4"
img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else "out/qr-rendered.png")
data, points, _ = cv2.QRCodeDetector().detectAndDecode(img)
ok = data == EXPECTED
print(f"{'PASS' if ok else 'FAIL'} T-13: decoded {data!r}")
sys.exit(0 if ok else 1)
