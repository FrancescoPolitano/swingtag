# Spike S1: does the delivery CSP let a phone open audio and video directly?
#
# PROVES: with the origin CSP (default-src 'none', no media-src) Chrome refuses
#         to load an .mp4 opened by direct navigation ("Loading media ...
#         violates ... default-src 'none'"). Adding media-src 'self' fixes it
#         for .mp4 and .m4a; images already pass through img-src 'self'.
# SHORTCUT: stdlib server, single-range parsing only, no HEAD, no caching,
#           Chrome desktop only (iOS Safari still to verify on a real device).
# Usage: CSP="..." python3 server.py <dir> <port>
import http.server, os, re, sys
CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; "
       "object-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
CSP = os.environ.get("CSP", CSP)
TYPES = {".m4a": "audio/mp4", ".mp4": "video/mp4", ".jpg": "image/jpeg", ".html": "text/html; charset=utf-8"}
class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return self.send_error(404)
        data = open(path, "rb").read()
        ctype = TYPES.get(os.path.splitext(path)[1], "application/octet-stream")
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range", ""))
        if m:
            start = int(m.group(1)); end = int(m.group(2) or len(data) - 1)
            self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            body = data[start:end + 1]
        else:
            self.send_response(200); body = data
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Security-Policy", CSP); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
os.chdir(sys.argv[1]); http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
