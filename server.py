from flask import Flask, request, jsonify, send_from_directory
import os, requests, tempfile, uuid, shutil, subprocess

app = Flask(__name__)

# Output folder
OUT_DIR = os.path.abspath("output")
os.makedirs(OUT_DIR, exist_ok=True)

# FFmpeg
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG = "ffmpeg"

def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for c in r.iter_content(8192):
            f.write(c)

def merge_videos(paths, out_path):
    temp = tempfile.mkdtemp()
    filelist = os.path.join(temp, "list.txt")

    with open(filelist, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")

    cmd = [
        FFMPEG,
        "-f", "concat",
        "-safe", "0",
        "-i", filelist,
        "-c", "copy",
        out_path
    ]

    try:
        subprocess.check_call(cmd)
    except:
        cmd = [
            FFMPEG,
            "-f", "concat",
            "-safe", "0",
            "-i", filelist,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            out_path
        ]
        subprocess.check_call(cmd)

    shutil.rmtree(temp, ignore_errors=True)

# ------------------------------------
# ✔️ MERGE ENDPOINT (100% WORKING)
# ------------------------------------
@app.route("/merge", methods=["POST"])
def merge_api():
    data = request.get_json(force=True) or {}
    urls = data.get("urls", [])

    if not urls or len(urls) < 2:
        return jsonify({"error": "Send at least 2 URLs"}), 400

    tmp = tempfile.mkdtemp()
    local_paths = []

    try:
        for i, u in enumerate(urls):
            dest = os.path.join(tmp, f"part{i}.mp4")
            download_file(u, dest)
            local_paths.append(dest)

        out_name = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join(OUT_DIR, out_name)

        merge_videos(local_paths, out_path)

        merged_url = request.url_root.rstrip("/") + "/output/" + out_name
        return jsonify({"merged_url": merged_url})

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

@app.route("/output/<path:filename>")
def serve_file(filename):
    return send_from_directory(OUT_DIR, filename)

@app.route("/")
def home():
    return jsonify({
        "ok": True,
        "service": "PrimeEdge Merge API",
        "endpoints": ["/merge"]
    })
