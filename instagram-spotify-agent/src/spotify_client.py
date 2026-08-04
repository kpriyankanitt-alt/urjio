"""Spotify access via spotipy (official Web API, OAuth Authorization Code flow)."""
import os
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth

TOKEN_CACHE = Path(__file__).resolve().parent.parent / ".spotify_token_cache"

SCOPE = "playlist-modify-private playlist-modify-public"


def build_client() -> spotipy.Spotify:
    auth_manager = SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=os.environ["SPOTIFY_REDIRECT_URI"],
        scope=SCOPE,
        cache_path=str(TOKEN_CACHE),
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_or_create_playlist(sp: spotipy.Spotify, playlist_id: str, playlist_name: str):
    me = sp.current_user()

    if playlist_id:
        return sp.playlist(playlist_id)

    offset = 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        for pl in page["items"]:
            if pl["name"].strip().lower() == playlist_name.strip().lower():
                return pl
        if not page["next"]:
            break
        offset += 50

    return sp.user_playlist_create(
        user=me["id"], name=playlist_name, public=False,
        description="Auto-added from Instagram 'music' saved collection",
    )


def existing_track_uris(sp: spotipy.Spotify, playlist_id: str) -> set:
    uris = set()
    offset = 0
    while True:
        page = sp.playlist_items(
            playlist_id, fields="items.track.uri,next", offset=offset, limit=100
        )
        for item in page["items"]:
            track = item.get("track")
            if track and track.get("uri"):
                uris.add(track["uri"])
        if not page.get("next"):
            break
        offset += 100
    return uris


def search_best_match(sp: spotipy.Spotify, title: str, artist: str):
    """Best-effort search: tries a scoped query first, falls back to a plain
    text query, and returns the top result (or None)."""
    if artist:
        query = f'track:{title} artist:{artist}'
        res = sp.search(q=query, type="track", limit=1)
        items = res["tracks"]["items"]
        if items:
            return items[0]

    res = sp.search(q=title, type="track", limit=1)
    items = res["tracks"]["items"]
    return items[0] if items else None
