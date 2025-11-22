from flask import Flask, request, jsonify
from youtube_service import get_video_id, fetch_transcript

app = Flask(__name__)

@app.route("/transcript", methods=["GET"])
def transcript_endpoint():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing YouTube URL"}), 400

    try:
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
