"""Serves demo.html on :8099 and forwards /v1/* to the model server (same origin, so the page can stream from it)."""
import http.server, os, sys, urllib.request

UP = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
HERE = os.path.dirname(os.path.abspath(__file__))
WIKI = r"D:\agentquant\data\wikitext-2-raw\wiki.train.raw"
DOC_CHARS = int(sys.argv[2]) if len(sys.argv) > 2 else 430000


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/doc/"):
            # two different long documents: slices of wikitext, about 95K tokens each
            n = int(self.path.rsplit("/", 1)[1])
            text = open(WIKI, encoding="utf-8").read()
            start = 200000 + n * 3000000
            data = text[start:start + DOC_CHARS].encode("utf-8")
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
            self.wfile.write(data); return
        name = "demo.html" if self.path.split("?")[0] in ("/", "/demo.html") else None
        if name is None:
            self.send_error(404); return
        data = open(os.path.join(HERE, name), "rb").read()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/result":
            open(os.path.join(HERE, "result.json"), "wb").write(body)
            self.send_response(200); self.end_headers(); return
        req = urllib.request.Request(UP + self.path, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-store")
            self.end_headers()
            for line in r:
                self.wfile.write(line); self.wfile.flush()


http.server.ThreadingHTTPServer(("127.0.0.1", 8099), H).serve_forever()
