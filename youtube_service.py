import functools
import os
import time
from collections import OrderedDict
import re
from urllib.parse import parse_qs, urlparse

import requests
from requests.adapters import HTTPAdapter
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
import redis

# Lightweight session with connection pooling to avoid recreating sockets on every call
_session = requests.Session()
_session.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=8))

# Pre-compiled regex for filename sanitization
_ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/*?:"<>|]')

# Preferred transcript languages in order
_PREFERRED_LANGS = ["en", "en-US", "en-GB"]

# Simple in-memory LRU cache for transcripts
_TRANSCRIPT_CACHE: OrderedDict[str, str] = OrderedDict()
_MAX_TRANSCRIPT_CACHE = 50 

_REDIS_URL = os.getenv("REDIS_URL")
_REDIS_LRU_KEY = "transcript:lru"
_REDIS_PREFIX = "transcript:cache:"


def _create_redis_client():
    if not _REDIS_URL:
        return None
    try:
        client = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        client.ping()
        return client
    except Exception:
        return None


_REDIS_CLIENT = _create_redis_client()


# ----------------------------
#   Proxy-Enabled API Client
# ----------------------------
def create_api():
    return YouTubeTranscriptApi(
        proxy_config=WebshareProxyConfig(
            proxy_username="mbrbdnsi",
            proxy_password="qlxjwi1vboda",
            filter_ip_locations=["us"]   # ensures fast & reliable US-based residential IPs
        )
    )


# Cache the API client so we do not rebuild it for every request
create_api = functools.lru_cache(maxsize=1)(create_api)


# ----------------------------
#   Extract Video ID
# ----------------------------
def get_video_id(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if "youtu.be" in hostname:
        # Short link format: https://youtu.be/<id>
        video_id = parsed.path.lstrip("/")
        if video_id:
            return video_id

    if "youtube.com" in hostname:
        # Standard format: https://www.youtube.com/watch?v=<id>
        qs = parse_qs(parsed.query)
        video_id = qs.get("v", [None])[0]
        if video_id:
            return video_id

    raise ValueError("Invalid YouTube URL")


# ----------------------------
#   Get Video Title
# ----------------------------
def get_video_title(video_id: str):
    oembed = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"

    try:
        r = _session.get(oembed, timeout=10)
        r.raise_for_status()
        return r.json().get("title", f"Video_{video_id}")
    except Exception:
        return f"Video_{video_id}"


# Title lookup is cacheable; titles do not change often and it avoids repeated network calls
get_video_title = functools.lru_cache(maxsize=128)(get_video_title)


# ----------------------------
#   Remove illegal filename chars
# ----------------------------
def sanitize_filename(title: str) -> str:
    return _ILLEGAL_FILENAME_CHARS.sub("", title)


def _cache_transcript(video_id: str, transcript: str) -> None:
    # Keep a tiny LRU of the last few transcripts to avoid refetching
    if video_id in _TRANSCRIPT_CACHE:
        _TRANSCRIPT_CACHE.move_to_end(video_id)
    _TRANSCRIPT_CACHE[video_id] = transcript
    if len(_TRANSCRIPT_CACHE) > _MAX_TRANSCRIPT_CACHE:
        _TRANSCRIPT_CACHE.popitem(last=False)

    if _REDIS_CLIENT:
        try:
            pipe = _REDIS_CLIENT.pipeline()
            pipe.lrem(_REDIS_LRU_KEY, 0, video_id)
            pipe.lpush(_REDIS_LRU_KEY, video_id)
            pipe.ltrim(_REDIS_LRU_KEY, 0, _MAX_TRANSCRIPT_CACHE - 1)
            pipe.set(f"{_REDIS_PREFIX}{video_id}", transcript)
            pipe.execute()

            # prune keys not present in the trimmed LRU list (keeps storage bounded)
            allowed_ids = set(_REDIS_CLIENT.lrange(_REDIS_LRU_KEY, 0, -1))
            for key in _REDIS_CLIENT.scan_iter(f"{_REDIS_PREFIX}*"):
                vid = key.replace(_REDIS_PREFIX, "", 1)
                if vid not in allowed_ids:
                    _REDIS_CLIENT.delete(key)
        except Exception:
            # Ignore Redis errors and continue with local cache
            pass


def _get_cached_transcript(video_id: str):
    if video_id in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[video_id]

    if _REDIS_CLIENT:
        try:
            cached = _REDIS_CLIENT.get(f"{_REDIS_PREFIX}{video_id}")
            if cached:
                # Mirror into local cache for faster repeat access in-process
                _cache_transcript(video_id, cached)
                return cached
        except Exception:
            pass
    return None


# ----------------------------
#   Fetch Transcript (ONE STRING)
# ----------------------------
def fetch_transcript(video_id: str):
    cached = _get_cached_transcript(video_id)
    if cached is not None:
        return cached

    def _fetch_once():
        ytt = create_api()

        # List all available transcripts for the video
        transcript_list = ytt.list(video_id)

        # Prefer English; fallback to first available
        try:
            transcript = transcript_list.find_transcript(_PREFERRED_LANGS)
        except Exception:
            available = list(transcript_list)
            if not available:
                return {"error": "No transcripts available for this video."}
            transcript = available[0]

        # Fetch transcript data and handle both dict and object forms
        fetched = transcript.fetch()

        def _extract_text(snippet):
            if snippet is None:
                return ""
            # Newer youtube_transcript_api returns objects with .text
            text_attr = getattr(snippet, "text", None)
            if text_attr:
                return text_attr
            # Older versions return dicts
            if isinstance(snippet, dict):
                return snippet.get("text", "")
            return ""

        combined = " ".join(filter(None, (_extract_text(s) for s in fetched))).strip()
        return combined

    attempts = 0
    last_error = None
    while attempts < 4:  # initial attempt + up to 3 retries
        try:
            result = _fetch_once()
            if isinstance(result, dict) and result.get("error"):
                # Don't retry for deterministic errors like no transcripts
                return result
            _cache_transcript(video_id, result)
            return result
        except Exception as e:
            last_error = e
            attempts += 1
            if attempts >= 4:
                break
            # simple linear backoff
            time.sleep(0.5 * attempts)

    return {"error": f"{last_error}" if last_error else "Failed to fetch transcript"}
