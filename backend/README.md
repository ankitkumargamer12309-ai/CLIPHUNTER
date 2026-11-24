# CLIP HUNTER Backend

FastAPI backend foundation for local video upload and **manual timestamp-based** clip export.

## Current API

- `GET /` — basic service information
- `GET /health` — health check
- `POST /api/upload` — upload a video (default maximum 500 MB)
- `GET /api/videos` — list uploaded videos
- `GET /api/videos/{video_id}` — read uploaded-video metadata
- `POST /api/videos/{video_id}/clips` — create an MP4 clip from supplied start/end timestamps
- `GET /api/clips` — list generated clips
- `GET /api/clips/{clip_id}/download` — download a generated clip

Accepted upload extensions: MP4, MOV, MKV, WEBM, AVI.

## Important capability boundary

Clip export currently uses **manual start and end timestamps**. It is not AI highlight detection and does not yet identify exciting gaming moments, track players, detect facecam activity, or generate smart subtitles. Ratio conversion uses FFmpeg scale/pad behavior; it is not subject-aware reframing.

## Requirements

- Python 3.10 or newer
- FFmpeg installed on the backend host and available on PATH
- If FFmpeg is installed outside PATH, set `FFMPEG_PATH` to the executable path

The Python package requirements do not install the FFmpeg executable. If FFmpeg is unavailable, the clip endpoint returns HTTP 503.

## Run locally

```bash
cd backend
python -m venv .venv
```

Activate the environment:

- Windows: `.venv\\Scripts\\activate`
- macOS/Linux: `source .venv/bin/activate`

Install and start:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/health` for the health check and `http://127.0.0.1:8000/docs` for interactive API docs.

## Manual clip request example

Send JSON to `POST /api/videos/{video_id}/clips`:

```json
{
  "start_seconds": 12,
  "end_seconds": 32,
  "ratio": "9:16",
  "title": "My gaming clip"
}
```

Use a valid uploaded `video_id`. The selected interval must be positive and no longer than the endpoint's 180-second limit. Then call `GET /api/clips` to list exports and `GET /api/clips/{clip_id}/download` to retrieve one.

## Configuration

- `CLIPHUNTER_UPLOAD_DIR`: optional upload storage directory.
- `CLIPHUNTER_MAX_UPLOAD_BYTES`: maximum upload size in bytes (default 500 MB).
- `CLIPHUNTER_ALLOWED_ORIGINS`: comma-separated frontend origins. The default `*` is for development only; set the exact deployed frontend origin before production.
- `FFMPEG_PATH`: optional path to the FFmpeg executable when it is not available on PATH.

Uploaded videos, generated clips, and their runtime metadata are stored locally and should not be committed to Git.

## Deployment and security status

This backend has been committed as source code but has not yet been verified on a live hosted server. The current API does not enforce Firebase authentication tokens, so frontend sign-in alone does not protect API endpoints. Add server-side token verification and production storage/access controls before exposing it publicly.
