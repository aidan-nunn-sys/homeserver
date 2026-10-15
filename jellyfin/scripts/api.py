"""Minimal Jellyfin REST client (stdlib only)."""
import json
import urllib.error
import urllib.request


class ApiError(Exception):
    pass


class Client:
    def __init__(self, base_url, api_key, timeout=30):
        self.base = base_url.rstrip('/')
        self.key = api_key
        self.timeout = timeout

    def get(self, path):
        return self._request('GET', path)

    def post(self, path, body):
        return self._request('POST', path, body)

    def _request(self, method, path, body=None):
        path = path.lstrip('/')
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f'{self.base}/{path}', data=data, method=method)
        req.add_header('Authorization', f'MediaBrowser Token="{self.key}"')
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise ApiError(f'{method} {path.split("?")[0]} -> HTTP {e.code}') from None
        return json.loads(raw) if raw else None
