"""Print a sanitized copy of a jfa-go config.ini (for jellyfin/custom/jfa-go/config.example.ini)."""
import argparse
import configparser
import io
import sys
from pathlib import Path

import envfile
from sanitize import SECRET_KEY, Sanitizer

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = 'jfa'


def export_ini(text, sanitizer):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_string(text)
    raw = {section: dict(parser[section]) for section in parser.sections()}
    clean = sanitizer.sanitize(raw, CONTEXT)
    out = configparser.ConfigParser(interpolation=None)
    out.optionxform = str
    out.read_dict(clean)
    buf = io.StringIO()
    out.write(buf)
    return buf.getvalue()


def secret_names(new):
    # Passwords and keys stay on the server; only hosts and the like go to .env.
    return {name for name in new
            if name.startswith(CONTEXT.upper() + '_') and SECRET_KEY.search(name)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--env', type=Path, default=ROOT / '.env')
    args = parser.parse_args(argv)
    env = envfile.load(args.env)
    domains = [d.strip() for d in env.get('PRIVATE_DOMAINS', '').split(',') if d.strip()]
    s = Sanitizer(env, domains=domains)
    sys.stdout.write(export_ini(args.config.read_text(), s))
    skip = secret_names(s.new)
    envfile.append(args.env, {k: v for k, v in s.new.items() if k not in skip})


if __name__ == '__main__':
    main()
