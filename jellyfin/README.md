# Jellyfin config

The server's configuration lives in `snapshot/`, with every identifying value
(API keys, hosts, domains, users, paths) replaced by a `<PLACEHOLDER>`. The real
values live only in `jellyfin/.env`, which is never committed. Keep a private
backup of `.env` (for example in a password manager) — without it, secrets
have to be re-entered by hand.

## One-time setup (per clone)

```bash
cp jellyfin/.env.example jellyfin/.env   # then fill in the four values
git config core.hooksPath jellyfin/scripts/hooks
```

Create the API key in Jellyfin: Dashboard → API Keys → +, name it `config-snapshot`.

## Taking a snapshot

```bash
python3 jellyfin/scripts/export.py
git add -N jellyfin/snapshot && python3 jellyfin/scripts/check_secrets.py --all
git add jellyfin/snapshot && git commit -m "jellyfin: snapshot"
```

The pre-commit hook blocks the commit if anything identifying slipped through.

## Making a change (so it can be reverted)

1. `export.py`, commit `jellyfin: snapshot before <change>`.
2. Make the change (files in `custom/` and/or the dashboard).
3. `export.py`, commit `jellyfin: <change>`.

To undo: `git revert <commit>`, then
`python3 jellyfin/scripts/restore.py` (dry run) and `--apply`.
If the change installed a plugin, uninstall it in Dashboard → Plugins and restart.

## Custom additions

- [`custom/tile-rotator/`](custom/tile-rotator/README.md): gives the library
  tiles a new random backdrop every 6 hours (runs as a container on the LAN).
- [`custom/home-curator/`](custom/home-curator/README.md): refreshes the
  "Trending Now" collection and the Media Bar's "Featured" playlist daily
  (systemd timer inside the Jellyfin LXC).

## Rebuilding a server from scratch

1. Install the Jellyfin version in `snapshot/server.json` (`Version`).
2. Create the users with the same names as in `.env` (`USER_1`, `USER_2`, …).
3. Create each library from `snapshot/libraries.json` with the same name, type and
   folders (`<MEDIA_ROOT>` = `MEDIA_ROOT` in `.env`).
4. Dashboard → Plugins → Repositories: add every entry in `snapshot/repositories.json`.
5. Install every plugin in `snapshot/plugins.json` whose `Status` is not
   `Superseded`, at the listed `Version`; leave `Disabled` ones disabled.
6. Restart Jellyfin.
7. Create an API key, put it and the new URL in `.env`.
8. `python3 jellyfin/scripts/restore.py` — read the list, then run again with `--apply`.
9. Restart Jellyfin, then run `restore.py` once more: it should print `no changes`.

## What is not covered

- Watch history, favourites, user passwords and the Jellyfin database.
- Media files, metadata and artwork.
- `snapshot/server.json` is a reference copy of the server settings; restore does
  not write it. Re-apply anything you need from it by hand in Dashboard → General.
- Per-user Home Screen Sections overrides that the plugin stores outside
  display preferences.
