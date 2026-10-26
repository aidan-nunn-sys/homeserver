import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_jfa import export_ini, secret_names
from sanitize import Sanitizer

IP = '.'.join(['192', '168', '0', '9'])
DOMAIN = 'example.org'


def make():
    return Sanitizer({}, domains=[DOMAIN])


class ExportIniTest(unittest.TestCase):
    def test_secret_keys_become_placeholders(self):
        out = export_ini('[email]\npassword = x\n\n[jellyfin]\npassword = y\n', make())
        self.assertIn('password = <JFA_EMAIL_PASSWORD>', out)
        self.assertIn('password = <JFA_JELLYFIN_PASSWORD>', out)
        self.assertNotIn('= x', out)
        self.assertNotIn('= y', out)

    def test_urls_and_ips_sanitized(self):
        out = export_ini(f'[jellyfin]\nserver = http://{IP}:8096\n', make())
        self.assertIn('server = http://<HOST_1>:8096', out)
        self.assertNotIn(IP, out)

    def test_domain_and_email_sanitized(self):
        out = export_ini(f'[ui]\njfa_url = https://join.{DOMAIN}\n'
                         f'[email]\naddress = noreply@{DOMAIN}\n', make())
        self.assertNotIn(DOMAIN, out)

    def test_non_secret_values_kept(self):
        out = export_ini('[password_validation]\nlength = 10\n', make())
        self.assertIn('length = 10', out)

    def test_section_order_preserved(self):
        out = export_ini('[b]\nx = 1\n\n[a]\ny = 2\n', make())
        self.assertLess(out.index('[b]'), out.index('[a]'))

    def test_secrets_not_returned_for_saving(self):
        s = make()
        export_ini(f'[email]\npassword = x\n[jellyfin]\nserver = http://{IP}\n', s)
        self.assertEqual(secret_names(s.new), {'JFA_EMAIL_PASSWORD'})


if __name__ == '__main__':
    unittest.main()
