import base64
from flask import Flask, request, jsonify
from youtube_service import get_video_id, fetch_transcript
from flask_cors import CORS

app = Flask(__name__)

# Allow all domains to access this API
CORS(app, resources={r"/*": {"origins": "*"}})

def decode_url_if_base64(url):
    """
    Detects and decodes Base64-encoded URLs automatically.
    Returns original string if it's NOT valid Base64.
    """
    try:
        decoded = base64.b64decode(url).decode("utf-8")
        # basic validation that decoded output looks like a URL
        if decoded.startswith("http"):
            return decoded
        return url
    except Exception:
        return url


@app.route("/transcript", methods=["GET"])
def transcript_endpoint():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing YouTube URL"}), 400

    try:
        # auto-decode if Base64 encoded
        url = decode_url_if_base64(url)

        video_id = get_video_id(url)
        transcript = fetch_transcript(video_id)

        return jsonify({
            "video_id": video_id,
            "transcript": transcript
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
