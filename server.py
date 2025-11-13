from flask import Flask, request, jsonify, send_from_directory
import os, requests, tempfile, uuid, shutil, subprocess

# Auto download FFmpeg if missing
try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
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

    # Write ffmpeg concat filelist
    with open(filelist_path, "w") as f:
        for p in video_paths:
            f.write("file '{}'\n".format(p.replace("'", "\\'")))

    # Try stream copy first
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
        # fallback re-encode
        cmd = [
            FFMPEG_BIN,
            "-f", "concat",
            "-safe", "0",
            "-i", filelist_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
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
    urls = data.get("urls", [])

    if not urls or len(urls) < 2:
        return jsonify({"error": "Send at least 2 URLs"}), 400

    tmpdir = tempfile.mkdtemp()
    paths = []

    try:
        # Download all files
        for i, u in enumerate(urls):
            local = os.path.join(tmpdir, f"part{i}.mp4")
            download_file(u, local)
            paths.append(local)

        # Output file
        out_name = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join(OUTPUT_DIR, out_name)

        merge_videos(paths, out_path)

        merged_url = request.url_root.rstrip("/") + "/output/" + out_name

        return jsonify({"merged_url": merged_url})
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@app.route("/output/<filename>", methods=["GET"])
def serve_file(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "ok": True,
        "service": "PrimeEdge Merge API",
        "endpoints": ["/merge"]
    })
