import re
import time
import requests
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi


def get_video_id(url: str) -> str:
    """Extract a YouTube video ID from a YouTube URL."""
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    if "youtube.com" in url and "v=" in url:
        return url.split("v=")[1].split("&")[0]
    raise ValueError("Invalid YouTube URL: unable to extract video ID")


def get_video_title(video_id: str) -> str:
    """Fetch the video title using YouTube oEmbed (no API key required)."""
    oembed_url = (
        f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json"
    )
    try:
        response = requests.get(oembed_url, timeout=10)
        response.raise_for_status()
        return response.json().get("title", f"Video_{video_id}")
    except requests.exceptions.RequestException:
        return f"Video_{video_id}"


def sanitize_filename(title: str) -> str:
    """Remove characters that are invalid in filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", title)


def fetch_transcript(video_id: str):
    """
    Fetch YouTube transcript and return one clean combined string.
    """
    try:
        ytt_api = YouTubeTranscriptApi()

        # List available transcripts
        transcript_list = ytt_api.list(video_id)

        # Prefer English
        try:
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        except:
            all_available = list(transcript_list)
            if not all_available:
                return {"error": "No transcripts available"}
            transcript = all_available[0]

        # Fetch transcript object
        fetched = transcript.fetch()

        # Raw entries (list of dicts)
        raw_entries = fetched.to_raw_data()

        # Extract text and join into one string
        combined_text = " ".join(entry["text"] for entry in raw_entries)

        return combined_text

    except Exception as e:
        return {"error": str(e)}


def write_transcript_to_file(transcript_raw: list, output_file: str):
    """Save transcript snippets to a text file."""
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in transcript_raw:
            f.write(f"{entry['text']}\n")


def get_formatted_date() -> str:
    """Return a date string formatted like [January 15, 2025]."""
    return datetime.now().strftime("[%B %d, %Y]")
