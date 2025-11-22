import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig


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


# ----------------------------
#   Extract Video ID
# ----------------------------
def get_video_id(url: str) -> str:
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]

    if "youtube.com" in url and "v=" in url:
        return url.split("v=")[1].split("&")[0]

    raise ValueError("Invalid YouTube URL")


# ----------------------------
#   Get Video Title
# ----------------------------
def get_video_title(video_id: str):
    oembed = f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"

    try:
        r = requests.get(oembed, timeout=10)
        r.raise_for_status()
        return r.json().get("title", f"Video_{video_id}")
    except Exception:
        return f"Video_{video_id}"


# ----------------------------
#   Remove illegal filename chars
# ----------------------------
def sanitize_filename(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", title)


# ----------------------------
#   Fetch Transcript (ONE STRING)
# ----------------------------
def fetch_transcript(video_id: str):
    try:
        ytt = create_api()

        # List all available transcripts for the video
        transcript_list = ytt.list(video_id)

        # Prefer English; fallback to first available
        try:
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
        except:
            available = list(transcript_list)
            if not available:
                return {"error": "No transcripts available for this video."}
            transcript = available[0]

        # Fetch transcript data
        fetched = transcript.fetch()
        raw = fetched.to_raw_data()

        # Return as one clean string
        combined = " ".join(item["text"] for item in raw)

        return combined

    except Exception as e:
        return {"error": f"{e}"}
