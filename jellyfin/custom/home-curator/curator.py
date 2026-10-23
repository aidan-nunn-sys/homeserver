#!/usr/bin/env python3
"""Keep Jellyfin's "Trending Now" collection and Media Bar playlist fresh.

- Trending Now: titles trending on TMDB (via Jellyseerr's discover API) that
  are already in the library. The Collection Sections plugin shows it as a
  home screen row. (Home Screen Sections' own Top Ten section is disabled
  upstream in 3.0.3, so it is not used.)
- Featured playlist: what the Media Bar rotates through: trending titles,
  titles added in the last week, and a random pick of highly rated titles.

Nobody has to sign up for anything: Jellyseerr's URL and API key are read from
the Home Screen Sections plugin config, and the Jellyfin API key comes from
the environment (see curator.env.example). Standard library only.
"""

import json
import os
import random
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://localhost:8096").rstrip("/")
JELLYFIN_API_KEY = os.environ["JELLYFIN_API_KEY"]
PLAYLIST_OWNER = os.environ["PLAYLIST_OWNER"]  # Jellyfin username that owns the playlist
HSS_CONFIG = os.environ.get(
    "HSS_CONFIG",
    "/var/lib/jellyfin/plugins/configurations/Jellyfin.Plugin.HomeScreenSections.xml",
)
TRENDING_NAME = os.environ.get("TRENDING_COLLECTION", "Trending Now")
TRENDING_MAX = int(os.environ.get("TRENDING_MAX", "10"))  # per type (movies, shows)
PLAYLIST_NAME = os.environ.get("PLAYLIST_NAME", "Featured")
TRENDING_PAGES = int(os.environ.get("TRENDING_PAGES", "10"))
FEATURED_TRENDING = int(os.environ.get("FEATURED_TRENDING", "8"))
FEATURED_NEW = int(os.environ.get("FEATURED_NEW", "6"))
FEATURED_TOP_RATED = int(os.environ.get("FEATURED_TOP_RATED", "6"))
NEW_DAYS = int(os.environ.get("NEW_DAYS", "7"))
MIN_RATING = float(os.environ.get("MIN_RATING", "7.5"))
DRY_RUN = "--dry-run" in sys.argv


def log(msg):
    print(msg, flush=True)


def http(method, url, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def jf(method, path, params=None, body=None):
    url = JELLYFIN_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    headers = {"Authorization": f'MediaBrowser Token="{JELLYFIN_API_KEY}", Client="home-curator"'}
    if DRY_RUN and method != "GET":
        log(f"  [dry-run] {method} {path} {params or ''}")
        return None
    return http(method, url, headers, body)


def seerr_settings():
    root = ET.parse(HSS_CONFIG).getroot()
    url = (root.findtext("JellyseerrUrl") or "").strip().rstrip("/")
    key = (root.findtext("JellyseerrApiKey") or "").strip()
    if not url or not key:
        raise SystemExit("Jellyseerr URL/API key not set in Home Screen Sections config")
    if not url.startswith("http"):
        url = "http://" + url
    return url, key


def trending_tmdb(seerr_url, seerr_key):
    """Ordered list of (mediaType, tmdbId) trending this week that the library has."""
    out = []
    for page in range(1, TRENDING_PAGES + 1):
        data = http("GET", f"{seerr_url}/api/v1/discover/trending?page={page}&language=en",
                    {"X-Api-Key": seerr_key})
        for r in data.get("results", []):
            status = (r.get("mediaInfo") or {}).get("status")
            if r.get("mediaType") in ("movie", "tv") and status in (4, 5):  # partially/available
                out.append((r["mediaType"], str(r["id"])))
        if page >= data.get("totalPages", page):
            break
    return out


def library():
    items = jf("GET", "/Items", {
        "Recursive": "true",
        "IncludeItemTypes": "Movie,Series",
        "Fields": "ProviderIds,DateCreated,DateLastMediaAdded",
        "EnableImages": "false",
    })["Items"]
    by_tmdb = {}
    for it in items:
        tmdb = (it.get("ProviderIds") or {}).get("Tmdb")
        if tmdb:
            kind = "movie" if it["Type"] == "Movie" else "tv"
            by_tmdb[(kind, tmdb)] = it
    return items, by_tmdb


def parse_date(s):
    if not s:
        return None
    s = s.rstrip("Z")[:26]
    try:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def find_one(item_type, name, user_id=None):
    params = {"Recursive": "true", "IncludeItemTypes": item_type, "SearchTerm": name}
    if user_id:
        params["UserId"] = user_id
    for it in jf("GET", "/Items", params)["Items"]:
        if it["Name"] == name:
            return it["Id"]
    return None


def sync_collection(name, ids):
    cid = find_one("BoxSet", name)
    if not cid:
        log(f"Creating collection '{name}' with {len(ids)} items")
        jf("POST", "/Collections", {"Name": name, "Ids": ",".join(ids)})
        return
    current = {i["Id"] for i in jf("GET", "/Items", {"ParentId": cid})["Items"]}
    remove, add = current - set(ids), [i for i in ids if i not in current]
    if remove:
        jf("DELETE", f"/Collections/{cid}/Items", {"Ids": ",".join(remove)})
    if add:
        jf("POST", f"/Collections/{cid}/Items", {"Ids": ",".join(add)})
    log(f"Collection '{name}': {len(ids)} items (+{len(add)} / -{len(remove)})")


def playlist_entry_for(item):
    """Series can't go in a playlist without expanding to every episode, so use
    one episode; the Media Bar maps episodes back to their series."""
    if item["Type"] != "Series":
        return item["Id"]
    eps = jf("GET", f"/Shows/{item['Id']}/Episodes", {"Limit": 1, "UserId": owner_id()})
    return eps["Items"][0]["Id"] if eps and eps.get("Items") else None


_owner = None


def owner_id():
    global _owner
    if _owner is None:
        for u in jf("GET", "/Users"):
            if u["Name"] == PLAYLIST_OWNER:
                _owner = u["Id"]
        if _owner is None:
            raise SystemExit(f"Playlist owner '{PLAYLIST_OWNER}' not found")
    return _owner


def sync_playlist(name, items):
    uid = owner_id()
    entries = [e for e in (playlist_entry_for(i) for i in items) if e]
    pid = find_one("Playlist", name, uid)
    if not pid:
        log(f"Creating playlist '{name}' with {len(entries)} entries")
        jf("POST", "/Playlists", body={"Name": name, "Ids": entries, "UserId": uid, "MediaType": "Video"})
        return
    current = jf("GET", f"/Playlists/{pid}/Items", {"UserId": uid})["Items"]
    if current:
        jf("DELETE", f"/Playlists/{pid}/Items", {"EntryIds": ",".join(i["PlaylistItemId"] for i in current)})
    if entries:
        jf("POST", f"/Playlists/{pid}/Items", {"Ids": ",".join(entries), "UserId": uid})
    log(f"Playlist '{name}': {len(entries)} entries")


def main():
    seerr_url, seerr_key = seerr_settings()
    items, by_tmdb = library()
    log(f"Library: {len(items)} movies/series, {len(by_tmdb)} with TMDB ids")

    trending = []
    for key in trending_tmdb(seerr_url, seerr_key):
        it = by_tmdb.get(key)
        if it and it not in trending:
            trending.append(it)
    movies = [i for i in trending if i["Type"] == "Movie"][:TRENDING_MAX]
    shows = [i for i in trending if i["Type"] == "Series"][:TRENDING_MAX]
    log(f"Trending in library: {len(movies)} movies, {len(shows)} shows")
    if movies or shows:
        sync_collection(TRENDING_NAME, [i["Id"] for i in movies + shows])
    else:
        log(f"No trending titles matched; leaving '{TRENDING_NAME}' unchanged")

    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_DAYS)
    new = [i for i in items
           if (parse_date(i.get("DateLastMediaAdded") if i["Type"] == "Series" else i.get("DateCreated")) or cutoff) > cutoff]
    new.sort(key=lambda i: i.get("DateLastMediaAdded") or i.get("DateCreated") or "", reverse=True)
    rated = jf("GET", "/Items", {"Recursive": "true", "IncludeItemTypes": "Movie,Series",
                                 "MinCommunityRating": MIN_RATING, "EnableImages": "false"})["Items"]
    random.shuffle(rated)

    featured, seen = [], set()
    for group, n in ((trending, FEATURED_TRENDING), (new, FEATURED_NEW), (rated, FEATURED_TOP_RATED)):
        added = 0
        for it in group:
            if added >= n:
                break
            if it["Id"] not in seen:
                featured.append(it)
                seen.add(it["Id"])
                added += 1
    random.shuffle(featured)
    log(f"Featured: {len(featured)} titles")
    sync_playlist(PLAYLIST_NAME, featured)


if __name__ == "__main__":
    main()
