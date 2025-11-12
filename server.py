from flask import Flask, request, jsonify, send_from_directory
import os, subprocess, tempfile, uuid, shutil
from typing import List
import requests

# Try to fetch a local ffmpeg path or fall back to imageio-ffmpeg (auto-download)
FFMPEG_BIN = os.environ.get("FFMPEG_PATH")
if not FFMPEG_BIN:
    try:
        import imageio_ffmpeg as ioff
        FFMPEG_BIN = ioff.get_ffmpeg_exe()
    except Exception:
        FFMPEG_BIN = "ffmpeg"  # Hope it's on PATH

app = Flask(__name__)
OUT_DIR = os.path.abspath(os.environ.get("OUTPUT_DIR", "static/output"))
os.makedirs(OUT_DIR, exist_ok=True)

def download(url: str, dest: str):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

def concat_videos_ffmpeg(inputs: List[str], output_path: str):
    # Write a temporary file list for ffmpeg concat demuxer
    tmpdir = tempfile.mkdtemp()
    try:
        filelist = os.path.join(tmpdir, "filelist.txt")
        with open(filelist, "w", encoding="utf-8") as f:
            for p in inputs:
                # Ensure single quotes are escaped
                f.write(f"file '{p.replace(\"'\", \"'\\\\''\")}'\n")

        # Use stream copy to keep quality/fast merge; re-mux to MP4 (H.264 + AAC prefer)
        cmd = [
            FFMPEG_BIN,
            "-f", "concat",
            "-safe", "0",
            "-i", filelist,
            "-c", "copy",
            output_path
        ]
        # If stream-copy fails, fallback to re-encode
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            cmd = [
                FFMPEG_BIN, "-f", "concat", "-safe", "0", "-i", filelist,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@app.route("/merge", methods=["POST"])
def merge():
    data = request.get_json(force=True, silent=True) or {}
    urls = data.get("urls") or []
    if not isinstance(urls, list) or len(urls) < 2:
        return jsonify({"error": "Provide at least two video URLs in 'urls'."}), 400

    tmpdir = tempfile.mkdtemp()
    try:
        local_paths = []
        for i, u in enumerate(urls):
            dest = os.path.join(tmpdir, f"part_{i}.mp4")
            download(u, dest)
            local_paths.append(dest)

        out_name = f"{uuid.uuid4().hex}.mp4"
        out_path = os.path.join(OUT_DIR, out_name)
        concat_videos_ffmpeg(local_paths, out_path)

        merged_url = request.url_root.rstrip("/") + "/output/" + out_name
        resp = {"merged_url": merged_url}

        # Optional: return duration/size
        try:
            size_mb = os.path.getsize(out_path) / (1024*1024.0)
            resp["size_mb"] = round(size_mb, 2)
        except Exception:
            pass

        return jsonify(resp)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

@app.route("/output/<path:filename>", methods=["GET"])
def serve_output(filename):
    return send_from_directory(OUT_DIR, filename, as_attachment=False)

@app.route("/", methods=["GET"])
def root():
    return jsonify({"ok": True, "service": "PrimeEdge Merge API", "endpoints": ["/merge", "/output/<file>"]})
