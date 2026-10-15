import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import envfile


class EnvFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / '.env'

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_is_empty(self):
        self.assertEqual(envfile.load(self.path), {})

    def test_load_skips_comments_and_blank_lines(self):
        self.path.write_text('# note\n\nA=1\nB = two=2 \n')
        self.assertEqual(envfile.load(self.path), {'A': '1', 'B': 'two=2'})

    def test_last_duplicate_wins(self):
        self.path.write_text('A=1\nA=2\n')
        self.assertEqual(envfile.load(self.path), {'A': '2'})

    def test_append_adds_missing_newline(self):
        self.path.write_text('A=1')
        envfile.append(self.path, {'B': '2'})
        self.assertEqual(self.path.read_text(), 'A=1\nB=2\n')

    def test_append_creates_file_and_ignores_empty(self):
        envfile.append(self.path, {})
        self.assertFalse(self.path.exists())
        envfile.append(self.path, {'A': '1'})
        self.assertEqual(envfile.load(self.path), {'A': '1'})


if __name__ == '__main__':
    unittest.main()
