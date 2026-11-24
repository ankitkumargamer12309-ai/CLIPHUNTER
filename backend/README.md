# CLIP HUNTER Backend

FastAPI backend foundation for local video upload and **manual timestamp-based** clip export.

## Current API

- `GET /` — basic service information
- `GET /health` — public health check
- `GET /api/me` — verify the signed-in Firebase session and return its account UID/email
- `POST /api/upload` — upload a video (default maximum 500 MB)
- `GET /api/videos` — list uploaded videos
- `GET /api/videos/{video_id}` — read uploaded-video metadata
- `POST /api/videos/{video_id}/clips` — create an MP4 clip from supplied start/end timestamps
- `GET /api/clips` — list generated clips
- `GET /api/clips/{clip_id}/download` — download a generated clip

Accepted upload extensions: MP4, MOV, MKV, WEBM, AVI.

## Important capability boundary

Clip export currently uses **manual start and end timestamps**. It is not AI highlight detection and does not yet identify exciting gaming moments, track players, detect facecam activity, or generate smart subtitles. Ratio conversion uses FFmpeg scale/pad behavior; it is not subject-aware reframing.

## Run locally

Requirements: Python 3.10+ and FFmpeg available on PATH.

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

## Docker deployment

A Docker image is provided in `backend/Dockerfile`; it installs FFmpeg and the Python requirements. The root `render.yaml` provides a Render Blueprint for the API.

Deployment checklist:

1. Import the CLIP HUNTER GitHub repository into Render using the Blueprint.
2. Set `FIREBASE_SERVICE_ACCOUNT_JSON` to the Firebase Admin service-account JSON (keep it secret; never commit it), and set `CLIPHUNTER_ALLOWED_ORIGINS` to the exact public frontend origin (for example, the GitHub Pages site origin); do not use `*` for production.
3. Deploy and open `/health` on the generated backend URL.
4. Copy that backend URL into the Backend API address field on the clipper page.

**Storage warning:** uploaded videos, generated clips, and metadata currently live on the backend filesystem. Many hosted services use ephemeral filesystems, so data can disappear after a restart or redeploy. Configure persistent storage before relying on clip history or user uploads in production. Video and clip API routes now require a valid Firebase ID token. The backend verifies tokens with Firebase Admin using `FIREBASE_SERVICE_ACCOUNT_JSON` (or application-default credentials). The clipper page sends the signed-in user's token. Configure the same Firebase web-app values in both `login.html` and `clipper.html`; keep the service-account key only in the backend host's secret environment variables. The backend stores an `owner_uid` on each upload and clip and checks ownership on list, read, export, and download routes. These protections are implemented in code but still need live deployment and multi-user verification.

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
- `CLIPHUNTER_ALLOWED_ORIGINS`: comma-separated frontend origins. The default `*` is for development only.
- `FFMPEG_PATH`: optional path to the FFmpeg executable when it is not available on PATH.

Uploaded videos, generated clips, and runtime metadata are excluded from Git by `.gitignore`.
