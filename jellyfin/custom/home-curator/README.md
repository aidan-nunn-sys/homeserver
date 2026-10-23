# home-curator

Keeps two things on the Jellyfin home screen fresh, daily, with no accounts needed by users:

| What | Shown by | Source |
|---|---|---|
| **Trending Now** collection | a Collection Sections row (`UniqueId=TrendingNow`, `CollectionName=Trending Now`) | TMDB trending (via Jellyseerr's discover API), limited to titles already in the library, up to 10 movies + 10 shows |
| **Featured** playlist | Media Bar (hero banner), with `UseAvatarsFile=false` and `AvatarsPlaylist=Featured` | trending + added in the last 7 days + random highly rated (7.5+) |

Personal rows (Because You Watched, Hidden Gems, Decade, Studio, Finish These Collections) come from Home Screen Sections itself. Its built-in *Top Ten* section is disabled upstream in 3.0.3, which is why trending uses Collection Sections.

## Install (inside the Jellyfin LXC)

```bash
mkdir -p /opt/jellyfin-home-curator
cp curator.py /opt/jellyfin-home-curator/
cp curator.env.example /etc/jellyfin-home-curator.env   # fill in, then:
chown root:jellyfin /etc/jellyfin-home-curator.env && chmod 640 /etc/jellyfin-home-curator.env
cp jellyfin-home-curator.service jellyfin-home-curator.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now jellyfin-home-curator.timer
systemctl start jellyfin-home-curator.service && journalctl -u jellyfin-home-curator -n 30
```

Run it once **before** configuring the Collection Sections row: that plugin caches collections at Jellyfin startup, so the collection must exist, then restart Jellyfin.

`python3 curator.py --dry-run` (with the env vars exported) prints what it would change.

## Notes

- Jellyseerr's URL and API key are read from the Home Screen Sections config, so no extra secret is stored. Home Screen Sections 3.x needs the URL to include `http://`.
- Series are added to the playlist as a single episode; the Media Bar maps episodes back to the series. Adding a series directly would expand to every episode.
