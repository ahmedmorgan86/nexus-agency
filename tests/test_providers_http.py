import os
import json
import threading
import http.server
import socketserver
import unittest
from nexus_os.providers import ImageProvider

class TestProviderHttp(unittest.TestCase):
    def setUp(self):
        self.port = 8123
        handler = self._handler()
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        os.environ["IMAGE_PROVIDER_URL"] = f"http://127.0.0.1:{self.port}/generate"
        os.environ["IMAGE_PROVIDER_API_KEY"] = "test-key"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("IMAGE_PROVIDER_URL", None)
        os.environ.pop("IMAGE_PROVIDER_API_KEY", None)

    def _handler(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                resp = {"status": "OK", "url": "http://example.com/image.png"}
                data = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def log_message(self, *args):
                pass
        return H

    def test_provider_calls_http(self):
        p = ImageProvider()
        res = p.generate("test prompt")
        self.assertEqual(res.get("status"), "OK")
        self.assertIn("url", res)

if __name__ == "__main__":
    unittest.main()
