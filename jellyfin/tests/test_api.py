import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from api import ApiError, Client


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload=None):
        body = b'' if payload is None else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Cloudflare's bot rules reject urllib's default user agent with 403
        if self.headers.get('User-Agent', '').startswith('Python-urllib'):
            return self._send(403)
        if self.headers.get('Authorization') != 'MediaBrowser Token="k1"':
            return self._send(401)
        if self.path == '/Items?x=1':
            return self._send(200, {'ok': True})
        self._send(404)

    def do_POST(self):
        if 'Content-Length' not in self.headers:
            return self._send(411)
        raw = self.rfile.read(int(self.headers['Content-Length']))
        self.server.last_body = json.loads(raw) if raw else None
        self._send(204)

    def do_DELETE(self):
        self.server.last_delete = self.path
        self._send(204 if self.path == '/Items/x/Images/Primary' else 404)


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('localhost', 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://localhost:{cls.server.server_port}/'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_get_sends_token(self):
        self.assertEqual(Client(self.url, 'k1').get('Items?x=1'), {'ok': True})

    def test_error_hides_query(self):
        with self.assertRaises(ApiError) as ctx:
            Client(self.url, 'k1').get('Missing?userId=secret')
        self.assertEqual(str(ctx.exception), 'GET Missing -> HTTP 404')

    def test_post_sends_json_and_handles_empty_reply(self):
        self.assertIsNone(Client(self.url, 'k1').post('/Things', {'a': 1}))
        self.assertEqual(self.server.last_body, {'a': 1})


    def test_post_without_body_sends_empty_content(self):
        self.assertIsNone(Client(self.url, 'k1').post('Items/x/Refresh', None))
        self.assertIsNone(self.server.last_body)

    def test_delete(self):
        self.assertIsNone(Client(self.url, 'k1').delete('Items/x/Images/Primary'))
        self.assertEqual(self.server.last_delete, '/Items/x/Images/Primary')
        with self.assertRaises(ApiError) as ctx:
            Client(self.url, 'k1').delete('Items/y/Images/Primary')
        self.assertEqual(str(ctx.exception), 'DELETE Items/y/Images/Primary -> HTTP 404')

if __name__ == '__main__':
    unittest.main()
