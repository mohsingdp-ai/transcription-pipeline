"""Transcription service: upload an audio file, get text with per-segment timestamps."""

import os
from pathlib import Path
from typing import Literal

import av
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}

# Loaded once at startup. int8 keeps it fast on CPU; "auto" uses a GPU when one is available.
# One model instance, so concurrent requests queue; scale with more workers or a job queue.
model = WhisperModel(MODEL_SIZE, device="auto", compute_type="int8")
app = FastAPI(title="Transcriber")


@app.get("/")
def index():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
def transcribe(file: UploadFile, format: Literal["json", "srt"] = "json"):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    # Checked after the upload is spooled to disk; cap request size at the reverse proxy in production.
    if (file.size or 0) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_MB} MB")

    # Decode any format to 16 kHz mono, the input Whisper expects.
    # Whole file is held in memory (~230 MB per hour of audio); stream chunks if files get much longer.
    try:
        audio = decode_audio(file.file)
    except (av.error.FFmpegError, IndexError):  # IndexError: the file has no audio stream
        raise HTTPException(400, "Could not read audio from this file")

    # vad_filter skips silence; Whisper itself walks long audio in 30-second windows.
    segments, info = model.transcribe(audio, vad_filter=True)
    segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segments]

    if format == "srt":
        return PlainTextResponse(to_srt(segments), media_type="application/x-subrip")
    return {
        "language": info.language,
        "duration": round(info.duration, 2),
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
    }


def to_srt(segments: list[dict]) -> str:
    def timestamp(seconds: float) -> str:
        ms = round(seconds * 1000)
        return f"{ms // 3_600_000:02}:{ms // 60_000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    return "\n".join(
        f"{i}\n{timestamp(s['start'])} --> {timestamp(s['end'])}\n{s['text']}\n" for i, s in enumerate(segments, 1)
    )
