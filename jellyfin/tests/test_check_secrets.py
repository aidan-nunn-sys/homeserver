import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_secrets
import fixtures


class ScanTextTest(unittest.TestCase):
    def test_env_values_split_domains_and_drop_short(self):
        values = check_secrets.env_values({'PRIVATE_DOMAINS': 'a.example, b.example', 'X': 'abc'})
        self.assertEqual(values, ['a.example', 'b.example'])

    def test_finds_each_kind(self):
        text = '\n'.join(['ok', 'key ' + fixtures.SONARR_KEY, fixtures.IP,
                          fixtures.EMAIL_ADDR, fixtures.ITEM_ID])
        found = check_secrets.scan_text(text, [fixtures.SONARR_KEY], set())
        self.assertEqual(found, [(2, '.env value'), (3, 'private IP'), (4, 'email'),
                                 (5, 'unlisted id or key')])

    def test_env_value_matches_whole_words_only(self):
        self.assertEqual(check_secrets.scan_text('TITLE "Zorbleton" QuxPlorbState',
                                                 ['bleton', 'lorb'], set()), [])
        self.assertEqual(check_secrets.scan_text('"Owner": "bleton", x?token=lorb&y=1',
                                                 ['bleton', 'lorb'], set()), [(1, '.env value')])

    def test_version_line_starting_with_10_not_flagged(self):
        ten = '.'.join(['10', '0', '0', '9'])
        text = '    "Version": "10.11.5.0"\n  "TargetAbi": "10.11.0.0",\n"Host": "' + ten + '"'
        self.assertEqual(check_secrets.scan_text(text, [], set()), [(3, 'private IP')])

    def test_ip_in_url_flagged_versions_not(self):
        url = 'http://' + '.'.join(['172', '39', '0', '4']) + ':7878'
        self.assertEqual(check_secrets.scan_text(url + '\n"1.10.11.13"', [], set()), [(1, 'IP in URL')])

    def test_allowlisted_id_passes(self):
        self.assertEqual(check_secrets.scan_text(fixtures.ITEM_ID, [], {fixtures.ITEM_ID}), [])

    def test_dashed_guid_normalized_for_allowlist(self):
        self.assertEqual(check_secrets.scan_text(fixtures.PLUGIN_ID.upper(), [],
                                                 {fixtures.PLUGIN_ID.replace('-', '')}), [])

    def test_placeholders_pass(self):
        self.assertEqual(check_secrets.scan_text('"<HOST_1>:8989" <USER_1_ID>', [], set()), [])


class MainTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.dir.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'jellyfin').mkdir()
        (self.repo / 'jellyfin' / '.env').write_text('SECRET=' + fixtures.SONARR_KEY + '\n')

    def tearDown(self):
        self.dir.cleanup()

    def stage(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        subprocess.run(['git', '-C', str(self.repo), 'add', '-f', name], check=True)

    def test_clean_staged_file_passes(self):
        self.stage('jellyfin/a.json', '{"Url": "<HOST_1>"}')
        self.assertEqual(check_secrets.main(['--repo', str(self.repo)]), 0)

    def test_staged_secret_fails(self):
        self.stage('jellyfin/a.json', '{"Key": "' + fixtures.SONARR_KEY + '"}')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(check_secrets.main(['--repo', str(self.repo)]), 1)
        self.assertIn('jellyfin/a.json:1: .env value', out.getvalue())
        self.assertNotIn(fixtures.SONARR_KEY, out.getvalue())

    def test_files_outside_jellyfin_ignored(self):
        self.stage('other/a.txt', fixtures.IP)
        self.assertEqual(check_secrets.main(['--repo', str(self.repo)]), 0)

    def test_allowlist_from_index(self):
        self.stage('jellyfin/snapshot/ids-allowlist.json', '["' + fixtures.ITEM_ID + '"]')
        self.stage('jellyfin/snapshot/a.json', '{"Id": "' + fixtures.ITEM_ID + '"}')
        self.assertEqual(check_secrets.main(['--repo', str(self.repo)]), 0)


    def test_staged_uses_committed_allowlist(self):
        self.stage('jellyfin/snapshot/ids-allowlist.json', '["' + fixtures.ITEM_ID + '"]')
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=t', '-c', 'user.email=t',
                        'commit', '-qm', 'x', '--no-verify'], check=True)
        self.stage('jellyfin/snapshot/a.json', '{"Id": "' + fixtures.ITEM_ID + '"}')
        self.assertEqual(check_secrets.main(['--repo', str(self.repo)]), 0)

    def test_all_uses_working_tree_allowlist(self):
        self.stage('jellyfin/snapshot/ids-allowlist.json', '[]')
        self.stage('jellyfin/snapshot/a.json', '{"Id": "' + fixtures.ITEM_ID + '"}')
        (self.repo / 'jellyfin/snapshot/ids-allowlist.json').write_text('["' + fixtures.ITEM_ID + '"]')
        self.assertEqual(check_secrets.main(['--all', '--repo', str(self.repo)]), 0)

    def test_all_with_intent_to_add_allowlist(self):
        (self.repo / 'jellyfin/snapshot').mkdir(parents=True)
        (self.repo / 'jellyfin/snapshot/ids-allowlist.json').write_text('["' + fixtures.ITEM_ID + '"]')
        (self.repo / 'jellyfin/snapshot/a.json').write_text('{"Id": "' + fixtures.ITEM_ID + '"}')
        subprocess.run(['git', '-C', str(self.repo), 'add', '-N', 'jellyfin/snapshot'], check=True)
        self.assertEqual(check_secrets.main(['--all', '--repo', str(self.repo)]), 0)

if __name__ == '__main__':
    unittest.main()
