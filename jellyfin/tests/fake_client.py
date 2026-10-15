import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from api import ApiError


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.posts = []

    def get(self, path):
        if path not in self.responses:
            raise ApiError(f'GET {path.split("?")[0]} -> HTTP 404')
        return copy.deepcopy(self.responses[path])

    def post(self, path, body):
        self.posts.append((path, copy.deepcopy(body)))
        self.responses[path] = copy.deepcopy(body)
