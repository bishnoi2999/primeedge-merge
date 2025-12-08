from flask import Flask, request, jsonify, send_from_directory
import os, tempfile, uuid, shutil, subprocess, requests

# Auto FFmpeg download
try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG_BIN = "ffmpeg"

app = Flask(__name__)
OUTPUT_DIR = os.path.abspath("static/output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def download_file(url, dest_path):
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def merge_videos(video_paths, output_path):
    tmp = tempfile.mkdtemp()
    filelist_path = os.path.join(tmp, "videos.txt")

    with open(filelist_path, "w") as f:
        for p in video_paths:
            f.write(f"file '{p}'\n")

    # Stream-copy merge
    cmd = [
        FFMPEG_BIN,
        "-f", "concat",
        "-safe", "0",
        "-i", filelist_path,
        "-c", "copy",
        output_path
    ]

    try:
        subprocess.check_call(cmd)
    except Exception:
        # fallback encode
        cmd = [
            FFMPEG_BIN,
            "-f", "concat",
            "-safe", "0",
            "-i", filelist_path,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path
        ]
        subprocess.check_call(cmd)

    shutil.rmtree(tmp, ignore_errors=True)

@app.route("/merge", methods=["POST"])
def merge_api():
    data = request.get_json(force=True, silent=True) or {}
    urls = data.get("urls") or data.get("video_urls") or []

    if not isinstance(urls, list) or len(urls) < 2:
        return jsonify({"error": "Send at least 2 URLs in `urls`"}), 400

    tmpdir = tempfile.mkdtemp()
    local_paths = []

    try:
        # Download all video parts
        for i, u in enumerate(urls):
            dest = os.path.join(tmpdir, f"part{i}.mp4")
            download_file(u, dest)
            local_paths.append(dest)

        # Output file
        out_name = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        merge_videos(local_paths, out_path)

        merged_url = request.url_root.rstrip("/") + "/output/" + out_name

        return jsonify({"merged_url": merged_url})

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@app.route("/output/<filename>")
def serve_file(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "service": "PrimeEdge Merge API",
        "endpoints": ["/merge"]
    })
