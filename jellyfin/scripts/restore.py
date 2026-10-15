"""Push snapshot/ back to a Jellyfin server. Dry run by default; --apply writes."""
import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

import envfile
from api import Client
from export import plugin_filename
from sanitize import dashed, fill, norm_guid, slug

ROOT = Path(__file__).resolve().parents[1]
Change = namedtuple('Change', 'label path body differs')
NOT_CONFIGURABLE = {'Superseded', 'Disabled', 'NotSupported', 'Malfunctioned'}


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def resolve_values(client, env):
    values = dict(env)
    for lib in client.get('Library/VirtualFolders'):
        base = f"LIBRARY_{slug(lib['Name'])}"
        values[base + '_ID'] = norm_guid(lib['ItemId'])
        values[base + '_GUID'] = dashed(lib['ItemId'])
    live = {u['Name']: u['Id'] for u in client.get('Users')}
    for key, name in env.items():
        if re.fullmatch(r'USER_\d+', key) and name in live:
            values[key + '_ID'] = norm_guid(live[name])
            values[key + '_GUID'] = dashed(live[name])
    return values


def plan(client, snap, values):
    read = lambda name: json.loads((snap / name).read_text())
    changes, skipped = [], []

    branding = fill(read('branding.json'), values)
    branding['CustomCss'] = fill((snap / 'branding.css').read_text(), values)
    path = 'System/Configuration/branding'
    changes.append(Change('branding', path, branding, not same(branding, client.get(path))))

    installed = {norm_guid(p['Id']) for p in client.get('Plugins') if p['Status'] not in NOT_CONFIGURABLE}
    for p in read('plugins.json'):
        config_file = snap / 'plugins' / plugin_filename(p['Name'])
        if p['Status'] == 'Superseded' or not config_file.exists():
            continue
        if norm_guid(p['Id']) not in installed:
            skipped.append(f"plugin not installed: {p['Name']}")
            continue
        path = f"Plugins/{p['Id']}/Configuration"
        body = fill(json.loads(config_file.read_text()), values)
        changes.append(Change(f"plugin: {p['Name']}", path, body, not same(body, client.get(path))))

    live_libs = {lib['Name']: lib for lib in client.get('Library/VirtualFolders')}
    for lib in fill(read('libraries.json'), values):
        current = live_libs.get(lib['Name'])
        if not current:
            skipped.append(f"library missing: {lib['Name']}")
            continue
        live_opts = current.get('LibraryOptions', {})
        wanted = {k: v for k, v in lib['LibraryOptions'].items() if k != 'PathInfos'}
        compare = {k: v for k, v in live_opts.items() if k != 'PathInfos'}
        body = {'Id': current['ItemId'],
                'LibraryOptions': {**wanted, 'PathInfos': live_opts.get('PathInfos', [])}}
        changes.append(Change(f"library: {lib['Name']}", 'Library/VirtualFolders/LibraryOptions',
                              body, not same(wanted, compare)))

    live_tasks = {t['Key']: t for t in client.get('ScheduledTasks')}
    for task in fill(read('tasks.json'), values):
        current = live_tasks.get(task['Key'])
        if not current:
            skipped.append(f"task missing: {task['Name']}")
            continue
        changes.append(Change(f"task: {task['Name']}", f"ScheduledTasks/{current['Id']}/Triggers",
                              task['Triggers'], not same(task['Triggers'], current.get('Triggers', []))))

    live_users = {u['Name']: u['Id'] for u in client.get('Users')}
    for key, prefs in read('users-display.json').items():
        uid = live_users.get(fill(key, values))
        if not uid:
            skipped.append(f'user missing: {key}')
            continue
        path = f'DisplayPreferences/usersettings?userId={uid}&client=emby'
        body = fill(prefs, values)
        changes.append(Change(f'display prefs: {key}', path, body, not same(body, client.get(path))))

    return changes, skipped


def main(argv=None, client=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, default=ROOT / '.env')
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'snapshot')
    parser.add_argument('--apply', action='store_true', help='write changes (default: dry run)')
    args = parser.parse_args(argv)
    env = envfile.load(args.env)
    client = client or Client(env['JELLYFIN_URL'], env['JELLYFIN_API_KEY'])

    required = json.loads((args.snapshot / 'placeholders.json').read_text())
    values = resolve_values(client, env)
    missing = sorted(name for name in required if name not in values)
    if missing:
        sys.exit('cannot restore, no value for: ' + ', '.join(missing))

    changes, skipped = plan(client, args.snapshot, values)
    pending = [c for c in changes if c.differs]
    for change in pending:
        if args.apply:
            client.post(change.path, change.body)
            print(f'updated: {change.label}')
        else:
            print(f'would change: {change.label}')
    for reason in skipped:
        print(f'skipped: {reason}')
    if not pending:
        print('no changes')
    elif not args.apply:
        print('dry run; re-run with --apply to write')


if __name__ == '__main__':
    main()
