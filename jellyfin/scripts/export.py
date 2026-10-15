"""Export live Jellyfin config to snapshot/, replacing identifying values with placeholders."""
import argparse
import json
import re
import sys
from pathlib import Path

import envfile
from api import ApiError, Client
from sanitize import Sanitizer

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ['JELLYFIN_URL', 'JELLYFIN_API_KEY', 'PRIVATE_DOMAINS', 'MEDIA_ROOT']


def plugin_filename(name):
    return re.sub(r'[^A-Za-z0-9]+', '-', name).strip('-').lower() + '.json'


def export(client, env, out_dir):
    raw, skipped = fetch(client)
    # Two passes: an item ID kept in an *Id field must also be kept wherever
    # else it appears (e.g. a list named DefaultLocalVideos), whatever the order.
    first = sanitizer(raw, env)
    sanitize_all(first, raw)
    s = sanitizer(raw, env, known_ids=first.kept_ids)
    files, css = sanitize_all(s, raw)
    write(out_dir, files, css)
    return s.new, skipped


def fetch(client):
    raw = {'info': client.get('System/Info'),
           'users': [(u['Name'], u['Id']) for u in client.get('Users')],
           'libraries': sorted(client.get('Library/VirtualFolders'), key=lambda lib: lib['Name'])}
    raw['config'] = client.get('System/Configuration')
    raw['repositories'] = client.get('Repositories')
    raw['plugins'] = sorted(client.get('Plugins'), key=lambda p: (p['Name'], p['Version']))
    raw['plugin_configs'], skipped = {}, []
    for p in raw['plugins']:
        if p['Status'] == 'Superseded':
            continue
        try:
            raw['plugin_configs'][p['Name']] = client.get(f"Plugins/{p['Id']}/Configuration")
        except ApiError:
            skipped.append(p['Name'])
    raw['branding'] = client.get('System/Configuration/branding')
    raw['tasks'] = sorted(client.get('ScheduledTasks'), key=lambda t: t['Key'])
    raw['display'] = {name: client.get(f'DisplayPreferences/usersettings?userId={uid}&client=emby')
                      for name, uid in raw['users']}
    return raw, skipped


def sanitizer(raw, env, known_ids=()):
    domains = [d.strip() for d in env.get('PRIVATE_DOMAINS', '').split(',') if d.strip()]
    return Sanitizer(env, domains=domains, users=raw['users'],
                     libraries=[(lib['Name'], lib['ItemId']) for lib in raw['libraries']],
                     literals={'MEDIA_ROOT': env.get('MEDIA_ROOT', ''),
                               'JELLYFIN_DATA': raw['info'].get('ProgramDataPath', '')},
                     known_ids=known_ids)


def sanitize_all(s, raw):
    files = {}
    files['server.json'] = s.sanitize(
        {'Version': raw['info']['Version'], 'Configuration': raw['config']}, 'server')
    files['repositories.json'] = s.sanitize(raw['repositories'], 'repositories')
    files['plugins.json'] = s.sanitize(
        [{k: p.get(k) for k in ('Name', 'Id', 'Version', 'Status')} for p in raw['plugins']], 'plugins')
    for name, config in raw['plugin_configs'].items():
        files['plugins/' + plugin_filename(name)] = s.sanitize(config, name)

    branding = s.sanitize(raw['branding'], 'branding')
    css = branding.pop('CustomCss', None) or ''
    files['branding.json'] = branding

    files['libraries.json'] = s.sanitize([
        {'Name': lib['Name'], 'CollectionType': lib.get('CollectionType'),
         'Locations': lib.get('Locations', []), 'LibraryOptions': lib.get('LibraryOptions', {})}
        for lib in raw['libraries']], 'libraries')
    files['tasks.json'] = s.sanitize(
        [{'Key': t['Key'], 'Name': t['Name'], 'Triggers': t.get('Triggers', [])} for t in raw['tasks']],
        'tasks')
    files['users-display.json'] = s.sanitize(raw['display'], 'users')

    files['placeholders.json'] = sorted(s.used)
    files['ids-allowlist.json'] = sorted(s.kept_ids)
    return files, css


def write(out_dir, files, css):
    plugin_dir = out_dir / 'plugins'
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for stale in plugin_dir.glob('*.json'):
        if f'plugins/{stale.name}' not in files:
            stale.unlink()
    for name, obj in files.items():
        (out_dir / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')
    (out_dir / 'branding.css').write_text(css)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, default=ROOT / '.env')
    parser.add_argument('--out', type=Path, default=ROOT / 'snapshot')
    args = parser.parse_args(argv)
    env = envfile.load(args.env)
    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        sys.exit('missing in .env: ' + ', '.join(missing))
    client = Client(env['JELLYFIN_URL'], env['JELLYFIN_API_KEY'])
    new, skipped = export(client, env, args.out)
    envfile.append(args.env, new)
    print(f'snapshot written to {args.out}; {len(new)} new value(s) saved to {args.env.name}')
    for name in skipped:
        print(f'no readable configuration: {name}')


if __name__ == '__main__':
    main()
