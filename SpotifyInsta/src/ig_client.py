"""Instagram access via instagrapi (unofficial private API).

Only reads data belonging to the logged-in account (its own Saved
Collections). There is no official Graph API surface for Saved Collections,
for any account type, so this is the only way to fetch this data
programmatically.
"""
import json
import os
import time
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, LoginRequired

SESSION_FILE = Path(__file__).resolve().parent.parent / "ig_session.json"


def _challenge_code_handler(username, choice):
    code = os.environ.get("IG_CHALLENGE_CODE")
    if not code:
        raise RuntimeError(
            "Instagram is asking for a verification code (challenge). "
            "Check email/SMS on the account, then rerun with "
            "IG_CHALLENGE_CODE=<code> set."
        )
    return code


def build_client() -> Client:
    cl = Client()
    # Space out requests to look less like a scripted burst.
    cl.delay_range = [1, 3]
    cl.challenge_code_handler = _challenge_code_handler
    return cl


def login(username: str, password: str) -> Client:
    cl = build_client()

    if SESSION_FILE.exists():
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            cl.get_timeline_feed()  # cheap call to confirm the session is alive
            return cl
        except LoginRequired:
            pass  # fall through to a fresh login
        except Exception:
            pass  # session file stale/corrupt, fall through to fresh login

    two_fa_code = os.environ.get("IG_2FA_CODE")
    try:
        if two_fa_code:
            cl.login(username, password, verification_code=two_fa_code)
        else:
            cl.login(username, password)
    except TwoFactorRequired as exc:
        raise RuntimeError(
            "Instagram requires a 2FA code for this account. Get the code "
            "from your authenticator app/SMS, then rerun with "
            "IG_2FA_CODE=<code> set."
        ) from exc
    except ChallengeRequired as exc:
        raise RuntimeError(
            "Instagram is asking for a verification code (challenge). "
            "Check email/SMS on the account, then rerun with "
            "IG_CHALLENGE_CODE=<code> set."
        ) from exc

    cl.dump_settings(SESSION_FILE)
    return cl


def find_collection_id(cl: Client, collection_name: str):
    for collection in cl.collections(amount=0):
        if collection.name.strip().lower() == collection_name.strip().lower():
            return collection.pk
    return None


def _extract_music_metadata(raw_media: dict):
    """Pull (title, artist) out of a raw media_info_v1 JSON blob.

    Instagram exposes this only through undocumented fields that shift
    over time, so we try a few known shapes and give up cleanly.
    """
    clips_meta = raw_media.get("clips_metadata") or {}

    music_info = clips_meta.get("music_info") or {}
    asset = music_info.get("music_asset_info") or {}
    title = asset.get("title")
    artist = asset.get("display_artist") or asset.get("artist_name")
    if title:
        return title, artist

    original_sound = clips_meta.get("original_sound_info") or {}
    title = original_sound.get("original_audio_title")
    artist = (original_sound.get("ig_artist") or {}).get("username")
    if title:
        return title, artist

    return None, None


def get_saved_music_posts(cl: Client, collection_id):
    """Returns a list of dicts: {pk, code, title, artist, permalink}."""
    medias = cl.collection_medias(collection_id, amount=0)
    results = []

    for media in medias:
        title = artist = None

        # media_type 2 == video; reels/clips are the only saved posts that
        # carry soundtrack metadata.
        if media.media_type == 2:
            try:
                raw = cl.private_request(f"media/{media.id}/info/")
                items = raw.get("items") or []
                if items:
                    title, artist = _extract_music_metadata(items[0])
            except Exception:
                pass
            time.sleep(1)  # extra breathing room between per-media lookups

        results.append(
            {
                "pk": media.pk,
                "code": media.code,
                "permalink": f"https://www.instagram.com/p/{media.code}/",
                "title": title,
                "artist": artist,
            }
        )

    return results
