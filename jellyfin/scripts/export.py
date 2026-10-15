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
    info = client.get('System/Info')
    users = [(u['Name'], u['Id']) for u in client.get('Users')]
    libraries = sorted(client.get('Library/VirtualFolders'), key=lambda lib: lib['Name'])
    domains = [d.strip() for d in env.get('PRIVATE_DOMAINS', '').split(',') if d.strip()]
    s = Sanitizer(env, domains=domains, users=users,
                  libraries=[(lib['Name'], lib['ItemId']) for lib in libraries],
                  literals={'MEDIA_ROOT': env.get('MEDIA_ROOT', ''),
                            'JELLYFIN_DATA': info.get('ProgramDataPath', '')})

    files = {}
    files['server.json'] = s.sanitize(
        {'Version': info['Version'], 'Configuration': client.get('System/Configuration')}, 'server')
    files['repositories.json'] = s.sanitize(client.get('Repositories'), 'repositories')

    plugins = sorted(client.get('Plugins'), key=lambda p: (p['Name'], p['Version']))
    files['plugins.json'] = s.sanitize(
        [{k: p.get(k) for k in ('Name', 'Id', 'Version', 'Status')} for p in plugins], 'plugins')
    skipped = []
    for p in plugins:
        if p['Status'] == 'Superseded':
            continue
        try:
            config = client.get(f"Plugins/{p['Id']}/Configuration")
        except ApiError:
            skipped.append(p['Name'])
            continue
        files['plugins/' + plugin_filename(p['Name'])] = s.sanitize(config, p['Name'])

    branding = s.sanitize(client.get('System/Configuration/branding'), 'branding')
    css = branding.pop('CustomCss', None) or ''
    files['branding.json'] = branding

    files['libraries.json'] = s.sanitize([
        {'Name': lib['Name'], 'CollectionType': lib.get('CollectionType'),
         'Locations': lib.get('Locations', []), 'LibraryOptions': lib.get('LibraryOptions', {})}
        for lib in libraries], 'libraries')

    tasks = sorted(client.get('ScheduledTasks'), key=lambda t: t['Key'])
    files['tasks.json'] = s.sanitize(
        [{'Key': t['Key'], 'Name': t['Name'], 'Triggers': t.get('Triggers', [])} for t in tasks],
        'tasks')

    display = {name: client.get(f'DisplayPreferences/usersettings?userId={uid}&client=emby')
               for name, uid in users}
    files['users-display.json'] = s.sanitize(display, 'users')

    files['placeholders.json'] = sorted(s.used)
    files['ids-allowlist.json'] = sorted(s.kept_ids)
    write(out_dir, files, css)
    return s.new, skipped


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
