# Experiment server for T-14, T-24: production CSP (with media-src) plus
# Content-Disposition inline on files, Range support. Usage: python3 e_serve.py <dir> <port>
import http.server, os, re, sys
CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; media-src 'self'; "
       "object-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
CSP = os.environ.get("CSP", CSP)
TYPES = {".pdf": "application/pdf", ".svg": "image/svg+xml", ".m4a": "audio/mp4", ".mp4": "video/mp4", ".jpg": "image/jpeg", ".html": "text/html; charset=utf-8"}
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
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes"); self.send_header("Content-Disposition", "inline; filename=\"" + os.path.basename(path) + "\"") if ctype.split(";")[0] in ("application/pdf", "video/mp4", "audio/mp4", "image/jpeg") else None
        self.send_header("Content-Security-Policy", CSP); self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
os.chdir(sys.argv[1]); http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), H).serve_forever()
