from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("CLIPHUNTER_UPLOAD_DIR", str(BASE_DIR / "uploads")))
METADATA_DIR = BASE_DIR / "data"
MAX_UPLOAD_BYTES = int(os.getenv("CLIPHUNTER_MAX_UPLOAD_BYTES", str(500 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="CLIP HUNTER API",
    version="0.1.0",
    description="Video intake API for the CLIP HUNTER clipping platform.",
)

# Development default. Restrict this to your deployed frontend domain before production.
allowed_origins = os.getenv("CLIPHUNTER_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "CLIP HUNTER API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "cliphunter-backend", "version": "0.1.0"}


@app.post("/api/upload", status_code=201)
async def upload_video(file: UploadFile = File(...)):
    original_name = Path(file.filename or "video").name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported video format. Use MP4, MOV, MKV, WEBM, or AVI.",
        )

    video_id = uuid.uuid4().hex
    destination = UPLOAD_DIR / f"{video_id}{extension}"
    total_bytes = 0

    try:
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
                    )
                output.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="The uploaded video is empty.")

        record = {
            "video_id": video_id,
            "original_name": original_name,
            "stored_name": destination.name,
            "size_bytes": total_bytes,
            "status": "uploaded",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": "Upload complete. AI clipping has not started yet.",
        }
        (METADATA_DIR / f"{video_id}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
        return record

    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save the uploaded video.") from exc
    finally:
        await file.close()


@app.get("/api/videos")
def list_uploaded_videos():
    videos = []
    for metadata_file in METADATA_DIR.glob("*.json"):
        try:
            videos.append(json.loads(metadata_file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    videos.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"videos": videos}


@app.get("/api/videos/{video_id}")
def get_uploaded_video(video_id: str):
    if not video_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid video ID.")
    metadata_file = METADATA_DIR / f"{video_id}.json"
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Video not found.")
    return json.loads(metadata_file.read_text(encoding="utf-8"))
