"""Give each library tile a fresh random backdrop every few hours.

Jellyfin draws a library's tile (darkened backdrop + library name) only when the
library has no image. Deleting the image and refreshing the library makes it
draw a new one from a random backdrop, so the change shows on every client.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import envfile
from api import ApiError, Client

REFRESH = 'Refresh?MetadataRefreshMode=Default&ImageRefreshMode=Default'


def rotate(client, log=print):
    failed = []
    for lib in client.get('Library/VirtualFolders'):
        item = f"Items/{lib['ItemId']}"
        try:
            try:
                client.delete(f'{item}/Images/Primary')
            except ApiError as e:
                if 'HTTP 404' not in str(e):
                    raise
            client.post(f'{item}/{REFRESH}', None)
            log(f"rotated: {lib['Name']}")
        except (ApiError, OSError) as e:
            failed.append(lib['Name'])
            log(f"failed: {lib['Name']} ({e})")
    return failed


def main(argv=None, client=None, sleep=time.sleep, environ=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='rotate once and exit')
    parser.add_argument('--env', type=Path, help='read settings from this file instead of the environment')
    args = parser.parse_args(argv)
    env = dict(os.environ if environ is None else environ)
    if args.env:
        env.update(envfile.load(args.env))
    if client is None:
        missing = [k for k in ('JELLYFIN_URL', 'JELLYFIN_API_KEY') if not env.get(k)]
        if missing:
            sys.exit('missing settings: ' + ', '.join(missing))
        client = Client(env['JELLYFIN_URL'], env['JELLYFIN_API_KEY'])

    if args.once:
        if rotate(client):
            sys.exit(1)
        return
    hours = float(env.get('ROTATE_HOURS', '6'))
    while True:
        try:
            rotate(client)
        except (ApiError, OSError) as e:
            print(f'error: {e}', flush=True)
        sleep(hours * 3600)


if __name__ == '__main__':
    main()
