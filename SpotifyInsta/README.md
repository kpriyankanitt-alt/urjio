# Instagram "music" collection -> Spotify playlist agent

Reads every Reel saved in your Instagram **Saved > music** collection, pulls
each one's soundtrack (title + artist), searches Spotify for the closest
match, and adds it to a target playlist. Writes a CSV report of every post
processed, including ones it couldn't resolve.

## Important caveats

- **Instagram has no official API for Saved Collections**, for any account
  type. This uses `instagrapi`, an unofficial client that logs in as your
  mobile app would. That's against Instagram's Terms of Service, even
  against your own account, and can trigger a login "challenge" (email/SMS
  verification) or, rarely, a temporary lock — especially the first time
  you log in from a new IP (like this session's cloud IP). Use it at your
  own risk, ideally with an account you're comfortable automating.
- **Only Reels carry soundtrack metadata.** Static photo saves are counted
  but skipped (marked `no_soundtrack_metadata` in the report) since there's
  no song to look up.
- **Matching is "best guess."** The agent adds Spotify's top search result
  for each extracted title/artist without a confidence check, per your
  instruction. Expect occasional wrong matches (covers, remixes, sound
  bites) — review the CSV report afterward.
- **This environment's disk is ephemeral.** `ig_session.json` and
  `.spotify_token_cache` let you avoid re-authenticating on every run, but
  they (and everything else here) disappear when this session ends. Copy
  the project out (or run it locally) if you want it to persist.

## 1. Create a Spotify Developer app (one-time)

1. Go to https://developer.spotify.com/dashboard and log in with your
   Spotify account.
2. Click **Create app**.
   - App name / description: anything, e.g. "IG Music Sync".
   - Redirect URI: `http://127.0.0.1:8080/callback` (must match
     `SPOTIFY_REDIRECT_URI` in `.env` exactly).
   - APIs used: check **Web API**.
3. Save. On the app's page, click **Settings** to find your **Client ID**
   and **Client secret**.

## 2. Configure

```bash
cd instagram-spotify-agent
cp .env.example .env
```

Fill in `.env`:
- `IG_USERNAME` / `IG_PASSWORD` — your Instagram login.
- `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` — from step 1.
- `SPOTIFY_PLAYLIST_NAME` (default `Instagram Music Saves`) — created
  automatically if it doesn't exist yet, or set `SPOTIFY_PLAYLIST_ID` to
  target an existing playlist (grab the ID from the playlist's share
  link: `open.spotify.com/playlist/<this part>`).

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Run

```bash
python src/main.py
```

The first Spotify auth will print a URL — open it, approve access, and
you'll be redirected to `127.0.0.1:8080/callback?code=...`. Since nothing
is listening on that port here, the page will fail to load — that's fine,
copy the **full redirected URL** from your browser's address bar and paste
it back into the terminal when spotipy asks for it.

If Instagram challenges the login, rerun with the code it emails/texts you:

```bash
IG_CHALLENGE_CODE=123456 python src/main.py
```

If your account has 2FA:

```bash
IG_2FA_CODE=123456 python src/main.py
```

Add `--dry-run` to see what would be added without actually modifying the
playlist:

```bash
python src/main.py --dry-run
```

## Output

Each run writes `output/run-<timestamp>.csv` with one row per saved post:
`permalink, ig_title, ig_artist, spotify_track, spotify_artist,
spotify_uri, status`. `status` is one of `added`, `already_in_playlist`,
`no_spotify_match`, `no_soundtrack_metadata`, or `would_add` (dry run).
