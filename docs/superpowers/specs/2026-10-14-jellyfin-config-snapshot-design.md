# Jellyfin config snapshot — design

Date: 2026-10-14
Status: approved in chat, awaiting written-spec review

## Goal

Keep the Jellyfin server's configuration (plugins, plugin settings, theme, home
screen layout, library options, scheduled tasks, injected scripts) in this repo so
that:

1. a fresh Jellyfin install can be rebuilt to look and behave the same by
   following `jellyfin/README.md`, and
2. any single change we make later (tile rotation, SmartLists, HoverTrailer, …)
   can be reverted with `git revert` plus a restore run.

This repo is **public**. Nothing identifying may be committed: no API keys,
tokens, passwords, internal IPs, domains, user names, user IDs, email addresses or
media paths.

## Non-goals

- Watch history, user accounts and passwords, and the Jellyfin database. These
  live in Jellyfin's database and are out of scope; the README says so.
- Media files and metadata images.
- Automating plugin installation. Plugins are installed by hand from the pinned
  list, because installs need a server restart and repository trust decisions.

## Layout

```
jellyfin/
  README.md            restore guide (fresh rebuild, then per-change revert)
  .gitignore           re-includes *.json / *.css under jellyfin/ (root ignores them)
  .env.example         every placeholder name, no values
  scripts/
    export.py          live API -> snapshot/, sanitized
    restore.py         snapshot/ -> live API, placeholders filled from .env
    check_secrets.py   fails if any .env value, IP or key-shaped string is staged
    hooks/pre-commit   runs check_secrets.py
  snapshot/            written only by export.py
    server.json        server version, selected system settings
    repositories.json  plugin repository URLs
    plugins.json       name, id, version, status of each plugin
    plugins/<name>.json  each plugin's configuration
    branding.css       Dashboard -> Branding custom CSS
    branding.json      remaining branding settings
    libraries.json     virtual folders and their LibraryOptions
    tasks.json         scheduled task triggers
    users-display.json per-user display prefs / home section overrides (users as placeholders)
    ids-allowlist.json GUIDs export deliberately kept
  custom/              hand-written changes, source of truth for our additions
```

The root `.gitignore` ignores `*.json`, `*.css` and `*.env`. `jellyfin/.gitignore`
re-includes `*.json` and `*.css` for this subtree and keeps `.env` ignored.

## Connection

- `JELLYFIN_URL` and `JELLYFIN_API_KEY` come from `jellyfin/.env`.
- The user creates the API key in Dashboard -> API Keys and writes it into `.env`
  themselves.
- Python 3 standard library only (`urllib`, `json`, `re`, `pathlib`). No installs.

## Sanitizing (layer 1, in export.py)

Export writes placeholders in place of real values and records each real value in
`.env` (appending new names, never printing values to the terminal).

| What | Rule | Placeholder |
|------|------|-------------|
| Secrets | key name matches `key|token|password|secret|apikey` (case-insensitive) and value is non-empty | `<PLUGIN_FIELD>` e.g. `<HOMESCREENSECTIONS_SONARR_APIKEY>` |
| Private IPs | RFC1918 / loopback IPv4, with optional port | `<HOST_N>` (stable per IP) |
| Domains | the user's own domains, listed in `.env` as `PRIVATE_DOMAINS` | `<DOMAIN_N>` |
| Users | user names and user IDs (GUIDs) from `/Users` | `<USER_N>` / `<USER_N_ID>` |
| Library IDs | GUIDs of virtual folders | `<LIBRARY_<Name>_ID>`, resolved by library name on restore |
| Other item IDs | collection/item GUIDs referenced in plugin configs | kept (opaque) and listed in `snapshot/ids-allowlist.json` |
| Paths | library paths, `/var/lib/jellyfin…`, `/mnt/…` prefixes | `<MEDIA_ROOT>`, `<JELLYFIN_DATA>` |
| Emails | regex | `<EMAIL_N>` |

Placeholder numbering is stable across exports (stored mapping in `.env`) so that
diffs only show real changes.

Output is pretty-printed JSON with sorted keys so `git diff` is readable.

## Leak check (layer 2, check_secrets.py)

Run as a pre-commit hook (installed by `git config core.hooksPath
jellyfin/scripts/hooks` — documented in README) and runnable by hand.

Fails the commit if any staged file under `jellyfin/` contains:

- any value from `jellyfin/.env` (length ≥ 4),
- a private IPv4 address,
- a 32+ character hex string (with or without dashes) not in
  `snapshot/ids-allowlist.json` (plugin GUIDs and kept item IDs, written by
  export; user IDs and secret values never enter it),
- an email address.

Prints file and line, never the matched value.

## Restore

`restore.py` reads `snapshot/` and `custom/`, substitutes placeholders from `.env`,
and POSTs:

- branding (CSS + settings),
- each installed plugin's configuration (skips plugins not installed and lists
  them),
- library options (matched by library name),
- scheduled task triggers,
- per-user display preferences (matched by placeholder -> real user name).

It defaults to a dry run that prints which settings would change, by name only;
`--apply` writes. Missing placeholders in `.env` stop the run before any write.

## Change workflow (how reverting works)

For every later change:

1. `export.py` -> commit `jellyfin: snapshot before <change>`.
2. Make the change (in `custom/` and/or the server).
3. `export.py` -> commit `jellyfin: <change>`.

Revert = `git revert <commit>` then `restore.py --apply`. If the change installed
a plugin, the README step for that change lists the uninstall.

## Testing

- `export.py` against the live server, then `check_secrets.py` on the result:
  must pass, and a manual grep for known IPs/domains/key prefixes must find
  nothing.
- Unit tests (stdlib `unittest`) for the sanitizer and the leak checker using
  synthetic fixtures (fake keys, fake IPs) — no real values in tests.
- `restore.py` dry run against the live server right after export must report
  zero changes (round-trip check).

## Order of work

1. This snapshot system + first baseline commit of today's state.
2. Then, each with its own short plan: library tile rotation (JS Injector,
   web only) -> SmartLists -> wizarr invites (`wizarr/docker-compose.yml`) ->
   HoverTrailer -> Posterizarr.

Separately (own commit): update the repo README to mention Jellyfin and remove
committed `.DS_Store` files.
