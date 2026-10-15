"""Fail if files under jellyfin/ contain identifying values.

Checks staged files by default (pre-commit hook); --all checks every tracked
file. Prints file:line and the kind of finding, never the value itself.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envfile
from sanitize import EMAIL, GUID, PRIVATE_IP, norm_guid

ALLOWLIST = 'jellyfin/snapshot/ids-allowlist.json'


def env_values(env):
    values = []
    for key, value in env.items():
        parts = value.split(',') if key == 'PRIVATE_DOMAINS' else [value]
        values += [p.strip() for p in parts if len(p.strip()) >= 4]
    return values


def scan_text(text, values, allowlist, check_ids=True):
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(v in line for v in values):
            findings.append((number, '.env value'))
        if PRIVATE_IP.search(line):
            findings.append((number, 'private IP'))
        if EMAIL.search(line):
            findings.append((number, 'email'))
        if check_ids and any(norm_guid(m.group(0)) not in allowlist for m in GUID.finditer(line)):
            findings.append((number, 'unlisted id or key'))
    return findings


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='check all tracked files, not just staged')
    parser.add_argument('--repo', type=Path)
    args = parser.parse_args(argv)
    repo = args.repo or Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').stdout.strip())

    if args.all:
        paths = git(repo, 'ls-files', '--', 'jellyfin/').stdout.split()
        read = lambda p: (repo / p).read_text(errors='replace')
    else:
        paths = git(repo, 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '--', 'jellyfin/').stdout.split()
        read = lambda p: git(repo, 'show', f':{p}').stdout

    env_path = repo / 'jellyfin' / '.env'
    if not env_path.exists():
        print('warning: jellyfin/.env not found; checking patterns only')
    values = env_values(envfile.load(env_path))
    listed = git(repo, 'show', f':{ALLOWLIST}')
    allowlist = {norm_guid(i) for i in json.loads(listed.stdout)} if listed.returncode == 0 else set()

    failed = False
    for path in paths:
        for number, kind in scan_text(read(path), values, allowlist,
                                      check_ids=not path.endswith('ids-allowlist.json')):
            print(f'{path}:{number}: {kind}')
            failed = True
    if failed:
        print('check_secrets: identifying values found; commit blocked')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
