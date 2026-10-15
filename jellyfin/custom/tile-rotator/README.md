# Library tile rotator

Every `ROTATE_HOURS` (default 6) this gives each library tile on the home
screen ("My Media") a new random backdrop. It deletes the library's image and
asks Jellyfin to refresh the library; Jellyfin then draws a new tile in its
usual style (darkened backdrop + library name). Because the image itself
changes, TVs and phones see it too, not just the web UI.

## Deploy (on any always-on Docker host on the LAN)

```bash
git clone https://github.com/aidan-nunn-sys/homeserver.git
cd homeserver/jellyfin/custom/tile-rotator
cp .env.example .env   # fill in JELLYFIN_URL and a new API key named tile-rotator
docker compose up -d
docker logs jellyfin-tile-rotator   # expect one "rotated: <library>" line per library
```

To rotate once by hand: `docker exec jellyfin-tile-rotator python /jellyfin/custom/tile-rotator/rotate.py --once`

## Update

`git pull && docker compose up -d --force-recreate`

## Undo

`docker compose down`, then delete the `tile-rotator` key in Dashboard → API
Keys. The tiles keep the last image they got, in Jellyfin's normal style.
