import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'custom' / 'tile-rotator'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import fixtures
import rotate
from api import ApiError
from fake_client import FakeClient

REFRESH = '/Refresh?MetadataRefreshMode=Default&ImageRefreshMode=Default'


def server(*names):
    responses = {'Library/VirtualFolders': [{'Name': n, 'ItemId': f'lib{i}'} for i, n in enumerate(names)]}
    for i, _ in enumerate(names):
        responses[f'Items/lib{i}/Images/Primary'] = 'png'
    return FakeClient(responses)


class FailingRefresh(FakeClient):
    def post(self, path, body):
        if path.startswith('Items/lib0/'):
            raise ApiError('POST Items/lib0/Refresh -> HTTP 500')
        super().post(path, body)


class StopLoop(Exception):
    pass


class RotateTest(unittest.TestCase):
    def test_deletes_then_refreshes_each_library(self):
        client = server('Collections', 'Movies')
        self.assertEqual(rotate.rotate(client, log=lambda _: None), [])
        self.assertEqual(client.deletes, ['Items/lib0/Images/Primary', 'Items/lib1/Images/Primary'])
        self.assertEqual([p for p, _ in client.posts], ['Items/lib0' + REFRESH, 'Items/lib1' + REFRESH])

    def test_library_without_image_is_still_refreshed(self):
        client = server('Movies')
        del client.responses['Items/lib0/Images/Primary']
        self.assertEqual(rotate.rotate(client, log=lambda _: None), [])
        self.assertEqual([p for p, _ in client.posts], ['Items/lib0' + REFRESH])

    def test_one_failure_does_not_stop_the_rest(self):
        client = FailingRefresh(server('Collections', 'Movies').responses)
        lines = []
        self.assertEqual(rotate.rotate(client, log=lines.append), ['Collections'])
        self.assertEqual(lines, ['failed: Collections (POST Items/lib0/Refresh -> HTTP 500)',
                                 'rotated: Movies'])

    def test_main_once(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rotate.main(['--once'], client=server('Movies'))
        self.assertEqual(out.getvalue(), 'rotated: Movies\n')

    def test_loop_survives_errors_and_sleeps_interval(self):
        client = server('Movies')
        client.responses.pop('Library/VirtualFolders')
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            if len(slept) == 2:
                raise StopLoop

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(StopLoop):
            rotate.main([], client=client, sleep=sleep, environ={'ROTATE_HOURS': '6'})
        self.assertEqual(slept, [6 * 3600, 6 * 3600])
        self.assertIn('error: GET Library/VirtualFolders -> HTTP 404', out.getvalue())

    def test_missing_settings_exit(self):
        with self.assertRaises(SystemExit) as ctx:
            rotate.main(['--once'], environ={})
        self.assertIn('JELLYFIN_URL', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
