"""Real loopback HTTP contract tests against a synthetic stub, NOT an LLM."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.providers import ProviderError, http_json


class HttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        records = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                records.append((self.path, body, self.headers.get("x-test-key")))
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/target")
                    self.end_headers()
                elif self.path == "/quota":
                    self.send_response(429)
                    self.end_headers()
                else:
                    encoded = json.dumps({"received": body}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_actual_json_round_trip_over_local_http(self):
        result = http_json(self.base + "/echo", {"text": "Pergunta sintética"}, {"x-test-key": "synthetic-only"}, 2)
        self.assertEqual(result, {"received": {"text": "Pergunta sintética"}})
        self.assertEqual(self.requests[0][2], "synthetic-only")

    def test_redirect_and_quota_do_not_follow_or_retry(self):
        for endpoint in ("/redirect", "/quota"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ProviderError):
                http_json(self.base + endpoint, {}, {"x-test-key": "synthetic-only"}, 2)
        self.assertEqual([r[0] for r in self.requests], ["/redirect", "/quota"])
