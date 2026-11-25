from __future__ import annotations
import cv2
from pathlib import Path

def detect_highlights(video_path: str | Path, clip_seconds: int = 25, max_candidates: int = 5, sample_every: float = 0.75):
    """Rank candidate high-motion windows; heuristic, not a trained game-event model."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not open video for highlight analysis.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = frames / fps if fps > 0 else 0
    if duration <= 0:
        cap.release()
        raise ValueError("Video duration could not be determined.")
    step = max(1, int(round(fps * sample_every))) if fps > 0 else 1
    scores, previous, index = [], None, 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                gray = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
                if previous is not None:
                    diff = cv2.absdiff(gray, previous)
                    motion = float(diff.mean()) / 255.0
                    scene_change = float((diff > 45).mean())
                    scores.append((index / fps if fps > 0 else len(scores) * sample_every,
                                   min(1.0, 0.75 * motion * 3.0 + 0.25 * scene_change)))
                previous = gray
            index += 1
    finally:
        cap.release()
    if not scores:
        return {"duration_seconds": round(duration, 2), "method": "frame-motion heuristic", "candidates": []}
    win = max(1, int(round(clip_seconds / sample_every)))
    ranked = []
    for i in range(len(scores)):
        left = max(0, i - win // 2)
        right = min(len(scores), left + win)
        segment = scores[left:right]
        if len(segment) < 2:
            continue
        vals = [v for _, v in segment]
        start, end = segment[0][0], min(duration, segment[-1][0] + sample_every)
        if end - start < 5:
            continue
        ranked.append({"start_seconds": round(start, 2), "end_seconds": round(end, 2),
                       "duration_seconds": round(end-start, 2),
                       "score": round(0.7 * sum(vals)/len(vals) + 0.3 * max(vals), 4)})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for item in ranked:
        if all(item["end_seconds"] <= old["start_seconds"] or item["start_seconds"] >= old["end_seconds"] for old in selected):
            selected.append(item)
            if len(selected) == max_candidates:
                break
    selected.sort(key=lambda x: x["start_seconds"])
    return {"duration_seconds": round(duration, 2), "method": "frame-motion + scene-change heuristic",
            "note": "Review candidates; this is not trained gaming-event AI.", "candidates": selected}
