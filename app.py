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


@app.route("/", methods=["GET"])
def home():
    # Simple inlined page to test the transcript API without extra templates
    return """
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>YouTube Transcript Tester</title>
  <style>
    :root {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #0b1221;
      color: #e9eef7;
      --card: #111a2f;
      --accent: #7ae8d8;
      --muted: #9fb1d1;
    }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px; }
    .card {
      width: min(960px, 100%);
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 14px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.35);
      padding: 28px 32px;
    }
    h1 { margin: 0 0 6px; letter-spacing: 0.3px; }
    p { margin: 0 0 18px; color: var(--muted); }
    label { font-weight: 600; display: block; margin-bottom: 8px; }
    input[type="text"] {
      width: 100%;
      padding: 12px 14px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.03);
      color: #fff;
      font-size: 15px;
      box-sizing: border-box;
    }
    input[type="text"]:focus { outline: 1px solid var(--accent); box-shadow: 0 0 0 4px rgba(122,232,216,0.12); }
    button {
      margin-top: 12px;
      padding: 12px 16px;
      border: none;
      border-radius: 10px;
      background: linear-gradient(120deg, var(--accent), #4fd4ff);
      color: #0b1221;
      font-weight: 700;
      cursor: pointer;
      transition: transform 120ms ease, box-shadow 120ms ease;
    }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    button:not(:disabled):hover { transform: translateY(-1px); box-shadow: 0 10px 30px rgba(79,212,255,0.25); }
    .status { margin-top: 14px; min-height: 20px; color: var(--muted); }
    textarea {
      margin-top: 18px;
      width: 100%;
      min-height: 280px;
      background: rgba(255,255,255,0.03);
      color: #e9eef7;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      padding: 14px;
      font-size: 14px;
      line-height: 1.5;
      box-sizing: border-box;
      resize: vertical;
    }
    .row { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
    .badge { padding: 6px 10px; background: rgba(122,232,216,0.12); color: var(--accent); border-radius: 999px; font-weight: 700; font-size: 12px; }
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"row\" style=\"justify-content: space-between;\">
      <div>
        <h1>Transcript Tester</h1>
        <p>Paste a YouTube link and fetch the transcript using the built-in API.</p>
      </div>
      <div class=\"badge\">Local Demo</div>
    </div>
    <label for=\"url\">YouTube URL</label>
    <input id=\"url\" type=\"text\" placeholder=\"https://www.youtube.com/watch?v=...\" />
    <button id=\"fetchBtn\">Fetch transcript</button>
    <div class=\"status\" id=\"status\"></div>
    <textarea id=\"output\" placeholder=\"Transcript will appear here...\" readonly></textarea>
  </div>

  <script>
    const btn = document.getElementById('fetchBtn');
    const urlInput = document.getElementById('url');
    const status = document.getElementById('status');
    const output = document.getElementById('output');

    async function fetchTranscript() {
      const url = urlInput.value.trim();
      if (!url) {
        status.textContent = 'Please enter a YouTube URL.';
        return;
      }
      btn.disabled = true;
      status.textContent = 'Fetching...';
      output.value = '';
      try {
        const resp = await fetch(`/transcript?url=${encodeURIComponent(url)}`);
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || 'Request failed');
        }
        if (data.error) {
          status.textContent = data.error;
          return;
        }
        status.textContent = data.video_id ? `Video ID: ${data.video_id}` : 'Success';
        output.value = typeof data.transcript === 'string' ? data.transcript : JSON.stringify(data.transcript, null, 2);
      } catch (err) {
        status.textContent = err.message || 'Something went wrong';
      } finally {
        btn.disabled = false;
      }
    }

    btn.addEventListener('click', fetchTranscript);
    urlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        fetchTranscript();
      }
    });
  </script>
</body>
</html>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
