# CLIP HUNTER Backend

Initial backend foundation using FastAPI.

## Included in this first version

- API health check: `GET /health`
- Video upload: `POST /api/upload`
- Uploaded-video list: `GET /api/videos`
- Uploaded-video metadata: `GET /api/videos/{video_id}`
- Upload limit defaults to 500 MB.
- Accepted formats: MP4, MOV, MKV, WEBM, AVI.

**Important:** this version stores uploaded videos and metadata only. It does not yet detect highlights, run AI models, cut clips, or export finished clips. Those processing features will be added in later stages.

## Run locally

Python 3.10 or newer is recommended.

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

## Configuration

- `CLIPHUNTER_UPLOAD_DIR`: optional upload storage directory.
- `CLIPHUNTER_MAX_UPLOAD_BYTES`: maximum upload size in bytes (default 500 MB).
- `CLIPHUNTER_ALLOWED_ORIGINS`: comma-separated frontend origins. The default `*` is for development only; set your exact deployed frontend origin before production.

Uploaded media and metadata are stored locally and are not committed to Git.
