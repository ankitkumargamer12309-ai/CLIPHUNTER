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


from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
import subprocess
import shutil

CLIP_DIR = BASE_DIR / "clips"
CLIP_DIR.mkdir(parents=True, exist_ok=True)
CLIP_METADATA_DIR = BASE_DIR / "clip_data"
CLIP_METADATA_DIR.mkdir(parents=True, exist_ok=True)

RATIO_DIMENSIONS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:5": (1080, 1350),
}


class ClipRequest(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    ratio: str = "9:16"
    title: str = Field(default="Gaming highlight", min_length=1, max_length=80)


def read_video_record(video_id: str):
    if not video_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid video ID.")
    metadata_file = METADATA_DIR / f"{video_id}.json"
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Video not found.")
    record = json.loads(metadata_file.read_text(encoding="utf-8"))
    source = UPLOAD_DIR / record["stored_name"]
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Stored video file is missing.")
    return record, source


@app.post("/api/videos/{video_id}/clips", status_code=201)
def create_timestamp_clip(video_id: str, request: ClipRequest):
    """Create a clip from user-selected timestamps; this is not AI highlight detection."""
    _, source = read_video_record(video_id)
    if request.end_seconds <= request.start_seconds:
        raise HTTPException(status_code=422, detail="End time must be after start time.")
    duration = request.end_seconds - request.start_seconds
    if duration > 180:
        raise HTTPException(status_code=422, detail="A clip cannot exceed 180 seconds.")
    if request.ratio not in RATIO_DIMENSIONS:
        raise HTTPException(status_code=422, detail="Unsupported ratio.")

    ffmpeg = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is not installed on the backend host. Install FFmpeg and set FFMPEG_PATH if needed.",
        )

    width, height = RATIO_DIMENSIONS[request.ratio]
    clip_id = uuid.uuid4().hex
    output = CLIP_DIR / f"{clip_id}.mp4"
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(request.start_seconds), "-i", str(source),
        "-t", str(duration), "-vf", video_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-movflags", "+faststart", str(output),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=504, detail="Clip processing timed out.") from exc

    if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="FFmpeg could not process this video. Check that the upload is a valid video.")

    clip_record = {
        "clip_id": clip_id,
        "video_id": video_id,
        "title": request.title,
        "ratio": request.ratio,
        "start_seconds": request.start_seconds,
        "end_seconds": request.end_seconds,
        "duration_seconds": round(duration, 2),
        "size_bytes": output.stat().st_size,
        "status": "ready",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "download_url": f"/api/clips/{clip_id}/download",
        "note": "Timestamp-based export. AI highlight detection is not enabled.",
    }
    (CLIP_METADATA_DIR / f"{clip_id}.json").write_text(
        json.dumps(clip_record, indent=2), encoding="utf-8"
    )
    return clip_record


@app.get("/api/clips")
def list_created_clips():
    clips = []
    for metadata_file in CLIP_METADATA_DIR.glob("*.json"):
        try:
            clips.append(json.loads(metadata_file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    clips.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"clips": clips}


@app.get("/api/clips/{clip_id}/download")
def download_created_clip(clip_id: str):
    if not clip_id.isalnum():
        raise HTTPException(status_code=400, detail="Invalid clip ID.")
    metadata_file = CLIP_METADATA_DIR / f"{clip_id}.json"
    output = CLIP_DIR / f"{clip_id}.mp4"
    if not metadata_file.is_file() or not output.is_file():
        raise HTTPException(status_code=404, detail="Clip not found.")
    record = json.loads(metadata_file.read_text(encoding="utf-8"))
    safe_title = "".join(ch for ch in record.get("title", "clip") if ch.isalnum() or ch in " -_").strip()
    return FileResponse(
        output,
        media_type="video/mp4",
        filename=f"{safe_title or 'clip'}.mp4",
    )
