import os
import uuid
import shutil
import tempfile
import subprocess
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
import requests

# ---------- FFmpeg detection ----------
FFMPEG_BIN = os.environ.get("FFMPEG_PATH")
if not FFMPEG_BIN:
    try:
        import imageio_ffmpeg
        FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_BIN = "ffmpeg"  # assume it's on PATH

# ---------- Flask + output directory ----------
app = Flask(__name__)

OUTPUT_DIR = os.path.abspath(os.environ.get("OUTPUT_DIR", "static/output"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------- Helpers ----------

def download_file(url: str, dest_path: str) -> None:
    """Download remote file to local path."""
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)


def seconds_to_srt_time(t: float) -> str:
    """Convert seconds to SRT timestamp."""
    ms = int(round(t * 1000))
    hours = ms // (1000 * 60 * 60)
    ms -= hours * 1000 * 60 * 60
    minutes = ms // (1000 * 60)
    ms -= minutes * 1000 * 60
    seconds = ms // 1000
    ms -= seconds * 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def build_srt_from_captions(captions: List[Dict[str, Any]], srt_path: str) -> None:
    """Build .srt subtitle file from your caption JSON."""
    lines = []
    idx = 1

    for block in captions:
        words = block.get("words") or []
        if not words:
            continue

        start = float(words[0].get("start", 0.0))
        end = float(words[-1].get("end", start + 0.5))

        text_parts = []
        for w in words:
            txt = str(w.get("text", ""))
            if w.get("highlight"):
                txt = f"{txt.upper()}"  # highlight style (simple)
            text_parts.append(txt)

        text_line = " ".join(text_parts)

        start_s = seconds_to_srt_time(start)
        end_s = seconds_to_srt_time(end)

        lines.append(str(idx))
        lines.append(f"{start_s} --> {end_s}")
        lines.append(text_line)
        lines.append("")  # blank line

        idx += 1

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> None:
    """Burn subtitles onto video using ffmpeg."""
    cmd = [
        FFMPEG_BIN,
        "-y",
        "-i", video_path,
        "-vf", f"subtitles={srt_path}",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


# ---------- API ROUTES ----------

@app.route("/merge", methods=["POST"])
def merge():
    """POST JSON:
    {
      "video_url": "...",
      "script": "...",
      "captions": [ { "words": [...] }, ... ]
    }
    """
    data = request.get_json(force=True, silent=True) or {}

    video_url = data.get("video_url")
    captions = data.get("captions")

    if not video_url:
        return jsonify({"error": "Missing 'video_url'"}), 400
    if not isinstance(captions, list) or not captions:
        return jsonify({"error": "Missing or invalid 'captions'"}), 400

    tmpdir = tempfile.mkdtemp()
    try:
        # 1) Download video
        input_video = os.path.join(tmpdir, "input.mp4")
        download_file(video_url, input_video)

        # 2) Build SRT
        srt_path = os.path.join(tmpdir, "captions.srt")
        build_srt_from_captions(captions, srt_path)

        # 3) Burn subtitles
        out_name = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        burn_subtitles(input_video, srt_path, out_path)

        merged_url = request.url_root.rstrip("/") + "/output/" + out_name
        return jsonify({"merged_url": merged_url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "ok": True,
        "service": "PrimeEdge Merge API",
        "endpoints": ["/merge", "/output/<file>"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
