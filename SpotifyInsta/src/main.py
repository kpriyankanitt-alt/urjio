"""Instagram 'music' saved-collection -> Spotify playlist agent.

1. Log into Instagram (your own account) and read the Saved collection
   named IG_COLLECTION_NAME (default: "music").
2. For each saved Reel, pull its soundtrack metadata (title/artist).
3. Search Spotify for the closest match and add it to the target playlist,
   skipping tracks already in the playlist.
4. Write a CSV report of what happened for every post, including the ones
   that couldn't be resolved.
"""
import csv
import datetime
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ig_client
import spotify_client

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def main():
    load_dotenv()

    ig_username = os.environ.get("IG_USERNAME")
    ig_password = os.environ.get("IG_PASSWORD")
    collection_name = os.environ.get("IG_COLLECTION_NAME", "music")
    dry_run = "--dry-run" in sys.argv

    if not ig_username or not ig_password:
        sys.exit("Set IG_USERNAME and IG_PASSWORD (see .env.example).")

    print(f"Logging into Instagram as {ig_username}...")
    cl = ig_client.login(ig_username, ig_password)

    print(f"Looking up Saved collection '{collection_name}'...")
    collection_id = ig_client.find_collection_id(cl, collection_name)
    if not collection_id:
        sys.exit(f"No Saved collection named '{collection_name}' was found.")

    print("Fetching saved posts and soundtrack metadata (this can be slow)...")
    posts = ig_client.get_saved_music_posts(cl, collection_id)
    print(f"Found {len(posts)} saved post(s) in '{collection_name}'.")

    print("Connecting to Spotify...")
    sp = spotify_client.build_client()

    playlist_id = os.environ.get("SPOTIFY_PLAYLIST_ID") or None
    playlist_name = os.environ.get("SPOTIFY_PLAYLIST_NAME", "Instagram Music Saves")
    playlist = spotify_client.get_or_create_playlist(sp, playlist_id, playlist_name)
    playlist_id = playlist["id"]
    print(f"Target playlist: {playlist['name']} ({playlist_id})")

    already_in_playlist = spotify_client.existing_track_uris(sp, playlist_id)

    rows = []
    to_add = []

    for post in posts:
        row = {
            "permalink": post["permalink"],
            "ig_title": post["title"] or "",
            "ig_artist": post["artist"] or "",
            "spotify_track": "",
            "spotify_artist": "",
            "spotify_uri": "",
            "status": "",
        }

        if not post["title"]:
            row["status"] = "no_soundtrack_metadata"
            rows.append(row)
            continue

        match = spotify_client.search_best_match(sp, post["title"], post["artist"])
        if not match:
            row["status"] = "no_spotify_match"
            rows.append(row)
            continue

        row["spotify_track"] = match["name"]
        row["spotify_artist"] = ", ".join(a["name"] for a in match["artists"])
        row["spotify_uri"] = match["uri"]

        if match["uri"] in already_in_playlist:
            row["status"] = "already_in_playlist"
        else:
            row["status"] = "added" if not dry_run else "would_add"
            to_add.append(match["uri"])
            already_in_playlist.add(match["uri"])

        rows.append(row)

    if to_add and not dry_run:
        # playlist_add_items caps at 100 URIs per call
        for i in range(0, len(to_add), 100):
            sp.playlist_add_items(playlist_id, to_add[i : i + 100])

    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = OUTPUT_DIR / f"run-{ts}.csv"
    with open(report_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    added = sum(1 for r in rows if r["status"] in ("added", "would_add"))
    skipped = len(rows) - added
    print(f"\nDone. {added} track(s) {'would be ' if dry_run else ''}added, "
          f"{skipped} skipped/unresolved.")
    print(f"Full report: {report_path}")


if __name__ == "__main__":
    main()
