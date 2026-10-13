FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv

RUN useradd --create-home app
USER app
WORKDIR /home/app

COPY --chown=app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Bake the model into the image so containers start without downloading it.
ARG WHISPER_MODEL=small
ENV WHISPER_MODEL=$WHISPER_MODEL
RUN .venv/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('$WHISPER_MODEL')"

COPY --chown=app main.py index.html ./
EXPOSE 8000
CMD [".venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
