# PrimeEdge Merge Microservice (Render Free)

Merge 2–3 short MP4 clips into one MP4 (H.264 + AAC) via a simple HTTP API.
Works on Render.com FREE plan. FFmpeg is fetched automatically via `imageio-ffmpeg`.

## Deploy (Render Free)

1. Create a new GitHub repo and upload these files:
   - `server.py`
   - `requirements.txt`
   - `Procfile`
   - `render.yaml` (optional, helpful for autosetup)
   - `README.md` (this file)

2. Go to https://dashboard.render.com/
   - Click **New +** → **Blueprint** (to use `render.yaml`) OR **Web Service** (manual).
   - Connect your GitHub repo.
   - Runtime: **Python**
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn server:app --preload --workers=1 --threads=2 --timeout=120`
   - Environment: **FREE** plan
   - Env Vars:
     - `OUTPUT_DIR` = `static/output`

3. Deploy. After a minute, you’ll get a base URL like:
   `https://primeedge-merge.onrender.com`

## API

### POST /merge
Merge 2+ MP4 URLs into one MP4.

**Request**
```json
{
  "urls": [
    "https://example.com/scene1.mp4",
    "https://example.com/scene2.mp4",
    "https://example.com/scene3.mp4"
  ]
}
```

**Response**
```json
{
  "merged_url": "https://primeedge-merge.onrender.com/output/abcd1234.mp4",
  "size_mb": 5.42
}
```

### GET /output/<file>
Serves the merged MP4. You can pass this URL back into n8n → Blotato "Upload media" node.

## n8n Cloud Integration

1. **After** your three Sora clips are ready, add an **HTTP Request** node:
   - Method: `POST`
   - URL: `https://YOUR-APP.onrender.com/merge`
   - Body → JSON:
     ```json
     {
       "urls": [
         "{{ $('Get video 1').item.json.fileUrl }}",
         "{{ $('Get video 2').item.json.fileUrl }}",
         "{{ $('Get video 3').item.json.fileUrl }}"
       ]
     }
     ```
   - Response will include: `merged_url`

2. Feed `merged_url` into your **Blotato → Upload media** node:
   - `mediaUrl` = `={{ $('Merge (HTTP)').item.json.merged_url }}`

3. Continue your existing flow:
   - OpenAI TTS narration
   - Add captions (Blotato caption field or overlay in your editor)
   - Create post (YouTube + Instagram)

## Notes
- If "copy codec" fails during concat, the service falls back to re-encoding (H.264/AAC).
- Files are written under `static/output`. On Render Free, disk space is ephemeral but sufficient for short-form clips.
- For cleanup/limits, you can add a cron to remove files older than N hours.

Happy merging!
