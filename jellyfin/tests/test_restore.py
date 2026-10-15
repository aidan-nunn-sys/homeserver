import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import export
import fixtures
import restore
from fake_client import FakeClient


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.snap = Path(self.dir.name) / 'snapshot'
        self.env = fixtures.env()
        new, _ = export.export(FakeClient(fixtures.responses()), self.env, self.snap)
        self.env.update(new)
        self.client = FakeClient(fixtures.responses())

    def tearDown(self):
        self.dir.cleanup()

    def changes(self):
        values = restore.resolve_values(self.client, self.env)
        return restore.plan(self.client, self.snap, values)

    def test_round_trip_has_no_changes(self):
        changes, skipped = self.changes()
        self.assertEqual([c.label for c in changes if c.differs], [])
        self.assertEqual(skipped, [])
        labels = [c.label for c in changes]
        self.assertEqual(labels, ['branding', 'plugin: Home Screen Sections', 'library: Movies',
                                  'task: Scan Media Library', 'display prefs: <USER_1>'])

    def test_changed_setting_is_detected_and_body_is_real(self):
        cfg_path = f'Plugins/{fixtures.PLUGIN_ID}/Configuration'
        self.client.responses[cfg_path]['Sonarr']['ApiKey'] = 'changed'
        changes, _ = self.changes()
        change = next(c for c in changes if c.differs)
        self.assertEqual(change.path, cfg_path)
        self.assertEqual(change.body['Sonarr']['ApiKey'], fixtures.SONARR_KEY)
        self.assertEqual(change.body['DefaultMoviesLibraryId'], fixtures.LIB_ID)

    def test_library_keeps_live_paths(self):
        self.client.responses['Library/VirtualFolders'][0]['LibraryOptions']['PathInfos'] = [{'Path': '/new'}]
        self.client.responses['Library/VirtualFolders'][0]['LibraryOptions']['EnableTrickplayImageExtraction'] = False
        changes, _ = self.changes()
        lib = next(c for c in changes if c.label == 'library: Movies')
        self.assertTrue(lib.differs)
        self.assertEqual(lib.body['Id'], fixtures.LIB_ID)
        self.assertEqual(lib.body['LibraryOptions']['PathInfos'], [{'Path': '/new'}])
        self.assertTrue(lib.body['LibraryOptions']['EnableTrickplayImageExtraction'])

    def test_library_ids_resolve_to_new_server(self):
        new_id = '12' * 16
        self.client.responses['Library/VirtualFolders'][0]['ItemId'] = new_id
        values = restore.resolve_values(self.client, self.env)
        self.assertEqual(values['LIBRARY_MOVIES_ID'], new_id)

    def test_missing_library_is_skipped(self):
        self.client.responses['Library/VirtualFolders'][0]['Name'] = 'Films'
        self.client.responses['Library/VirtualFolders'][0]['ItemId'] = fixtures.LIB_ID
        values = restore.resolve_values(self.client, self.env)
        values['LIBRARY_MOVIES_ID'] = fixtures.LIB_ID
        _, skipped = restore.plan(self.client, self.snap, values)
        self.assertIn('library missing: Movies', skipped)

    def test_uninstalled_plugin_is_skipped(self):
        self.client.responses['Plugins'] = []
        _, skipped = self.changes()
        self.assertIn('plugin not installed: Home Screen Sections', skipped)

    def test_missing_placeholder_aborts_without_posting(self):
        env_path = Path(self.dir.name) / '.env'
        env_path.write_text('\n'.join(f'{k}={v}' for k, v in self.env.items()
                                      if k != 'HOME_SCREEN_SECTIONS_SONARR_APIKEY') + '\n')
        with self.assertRaises(SystemExit) as ctx:
            restore.main(['--env', str(env_path), '--snapshot', str(self.snap), '--apply'],
                         client=self.client)
        self.assertIn('HOME_SCREEN_SECTIONS_SONARR_APIKEY', str(ctx.exception.code))
        self.assertEqual(self.client.posts, [])

    def test_apply_posts_only_changes(self):
        env_path = Path(self.dir.name) / '.env'
        env_path.write_text('\n'.join(f'{k}={v}' for k, v in self.env.items()) + '\n')
        self.client.responses['System/Configuration/branding']['CustomCss'] = ''
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            restore.main(['--env', str(env_path), '--snapshot', str(self.snap), '--apply'],
                         client=self.client)
        self.assertEqual([p for p, _ in self.client.posts], ['System/Configuration/branding'])
        self.assertEqual(out.getvalue(), 'updated: branding\n')


if __name__ == '__main__':
    unittest.main()
