import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import export
import fixtures
from fake_client import FakeClient


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.out = Path(self.dir.name) / 'snapshot'
        self.client = FakeClient(fixtures.responses())
        self.env = fixtures.env()

    def tearDown(self):
        self.dir.cleanup()

    def run_export(self):
        new, skipped = export.export(self.client, self.env, self.out)
        self.env.update(new)
        return new, skipped

    def read(self, name):
        return json.loads((self.out / name).read_text())

    def all_text(self):
        return '\n'.join(p.read_text() for p in sorted(self.out.rglob('*')) if p.is_file())

    def test_plugin_filename(self):
        self.assertEqual(export.plugin_filename('Home Screen Sections'), 'home-screen-sections.json')

    def test_writes_expected_files(self):
        self.run_export()
        names = sorted(str(p.relative_to(self.out)) for p in self.out.rglob('*') if p.is_file())
        self.assertEqual(names, [
            'branding.css', 'branding.json', 'ids-allowlist.json', 'libraries.json',
            'placeholders.json', 'plugins.json', 'plugins/home-screen-sections.json',
            'repositories.json', 'server.json', 'tasks.json', 'users-display.json'])

    def test_no_sensitive_value_in_output(self):
        self.run_export()
        text = self.all_text()
        for value in fixtures.SENSITIVE:
            self.assertNotIn(value, text)

    def test_plugin_config_placeholders(self):
        self.run_export()
        cfg = self.read('plugins/home-screen-sections.json')
        self.assertEqual(cfg['Sonarr']['ApiKey'], '<HOME_SCREEN_SECTIONS_SONARR_APIKEY>')
        self.assertEqual(cfg['DefaultMoviesLibraryId'], '<LIBRARY_MOVIES_ID>')
        self.assertEqual(cfg['PinnedItemId'], fixtures.ITEM_ID)
        self.assertIn(fixtures.ITEM_ID, self.read('ids-allowlist.json'))

    def test_new_env_holds_real_values(self):
        new, _ = self.run_export()
        self.assertEqual(new['HOME_SCREEN_SECTIONS_SONARR_APIKEY'], fixtures.SONARR_KEY)
        self.assertEqual(new['JELLYFIN_DATA'], '/srv/jf-data')
        self.assertEqual(new['USER_1'], 'alice')

    def test_branding_css_split_out(self):
        self.run_export()
        self.assertEqual((self.out / 'branding.css').read_text(),
                         '@import url("https://cdn.example.com/theme.css");')
        self.assertNotIn('CustomCss', self.read('branding.json'))

    def test_users_display_keyed_by_placeholder(self):
        self.run_export()
        self.assertEqual(list(self.read('users-display.json')), ['<USER_1>'])

    def test_placeholders_listed(self):
        self.run_export()
        names = self.read('placeholders.json')
        self.assertIn('HOME_SCREEN_SECTIONS_SONARR_APIKEY', names)
        self.assertIn('MEDIA_ROOT', names)
        self.assertEqual(names, sorted(names))

    def test_unreadable_plugin_config_is_skipped(self):
        _, skipped = self.run_export()
        self.assertEqual(skipped, ['Old Thing'])
        self.assertEqual(len(self.read('plugins.json')), 3)

    def test_stale_plugin_file_removed(self):
        (self.out / 'plugins').mkdir(parents=True)
        (self.out / 'plugins' / 'gone.json').write_text('{}')
        self.run_export()
        self.assertFalse((self.out / 'plugins' / 'gone.json').exists())

    def test_second_export_is_identical(self):
        self.run_export()
        first = self.all_text()
        new, _ = self.run_export()
        self.assertEqual(new, {})
        self.assertEqual(self.all_text(), first)


if __name__ == '__main__':
    unittest.main()
