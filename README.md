# Transcriber

Upload an audio file and get back the text, with start and end times for each segment.
It uses open-source Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)) running locally, so there's no paid API and no audio leaves the server.

## Run

```bash
uv sync
uv run uvicorn main:app --port 8000   # open http://localhost:8000
```

Or with Docker (the model is baked into the image, and it runs as a non-root user):

```bash
docker build -t transcriber .
docker run -p 8000:8000 transcriber
```

Settings: `WHISPER_MODEL` (default `small`; `large-v3` is more accurate but slower) and `MAX_UPLOAD_MB` (default `100`).

## API

| Endpoint | What it does |
|---|---|
| `POST /transcribe` | Multipart field `file`, which can be WAV, MP3, M4A, FLAC, OGG or WebM. Returns JSON. |
| `POST /transcribe?format=srt` | Same, but returns a subtitle (SRT) file. |
| `GET /health` | Liveness check. |
| `GET /` | Upload page. |

```bash
curl -F file=@samples/hello.wav localhost:8000/transcribe
```

```json
{
  "language": "en",
  "duration": 6.73,
  "text": "Hello, this is a short test of the transcription pipeline. The weather today is sunny and warm.",
  "segments": [
    {"start": 0.0, "end": 3.74, "text": "Hello, this is a short test of the transcription pipeline."},
    {"start": 4.06, "end": 6.34, "text": "The weather today is sunny and warm."}
  ]
}
```

Errors return a clear message:

| Code | Cause |
|---|---|
| 415 | File type not supported |
| 413 | File too large |
| 400 | File is corrupt, or has no audio track |

## Test

```bash
uv run pytest
```

This covers WAV and MP3 transcription, timestamps, SRT output and every error case, using the files in `samples/`.

## Design decisions

- **Model:** faster-whisper `small`, quantized to int8 (smaller numbers, so it runs faster on CPU). On a 12-core CPU it transcribes about 3× faster than real time: 2.5 minutes of audio took about 50 seconds. If a GPU is available it's used automatically.
- **Formats:** every input is decoded to 16 kHz mono, which is what Whisper expects. Decoding uses PyAV, which wraps ffmpeg and ships with faster-whisper, so there's no separate system install. After that there's only one code path.
- **Validation:** inputs are checked against a list of allowed extensions and a size cap. Files that are corrupt or have no audio are rejected before the model runs.
- **Long audio:** voice-activity detection (VAD) skips silence. Whisper reads the audio in 30-second windows and keeps the timestamps continuous across them.
- **Output:** JSON for other programs, SRT for subtitles.

## Limits and next steps

- **Requests wait for the result.** That's fine for a few minutes of audio. For hour-long files, use a background job: return a job ID right away, and let the client check back for the result.
- **The whole file is held in memory,** about 230 MB per hour of audio.
- **One model per process,** so requests that arrive together are handled one at a time. To handle more load, run more workers or use a GPU.
- **The size cap is checked after the upload arrives.** Also cap request size at the reverse proxy.
- **There's no login or rate limiting yet.** Add both before exposing this publicly.
