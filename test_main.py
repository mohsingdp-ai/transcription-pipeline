from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)
SAMPLES = Path(__file__).parent / "samples"


def upload(name, data=None, **params):
    data = (SAMPLES / name).read_bytes() if data is None else data
    return client.post("/transcribe", files={"file": (name, data)}, params=params)


@pytest.mark.parametrize("name", ["hello.wav", "hello.mp3"])
def test_transcribes_with_segment_timestamps(name):
    res = upload(name)
    assert res.status_code == 200
    body = res.json()
    assert body["language"] == "en"
    assert "weather today is sunny" in body["text"].lower()
    starts = [s["start"] for s in body["segments"]]
    assert starts == sorted(starts)
    assert all(s["start"] < s["end"] for s in body["segments"])


def test_srt_output():
    res = upload("hello.wav", format="srt")
    assert res.status_code == 200
    assert res.text.startswith("1\n00:00:00,000 --> 00:00:0")


def test_srt_timestamp_format():
    assert main.to_srt([{"start": 3725.5, "end": 3726.04, "text": "hi"}]) == "1\n01:02:05,500 --> 01:02:06,040\nhi\n"


@pytest.mark.parametrize(
    ("name", "data", "status"),
    [
        ("notes.txt", b"hello", 415),  # wrong extension
        ("broken.wav", b"not really audio", 400),  # corrupt file
        ("no_audio.webm", None, 400),  # valid file, but video only
    ],
)
def test_rejects_bad_input(name, data, status):
    assert upload(name, data).status_code == status


def test_rejects_too_large(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 0)
    assert upload("hello.wav").status_code == 413


def test_health_and_ui():
    assert client.get("/health").json() == {"status": "ok"}
    assert "<form" in client.get("/").text
