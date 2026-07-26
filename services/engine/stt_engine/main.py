from __future__ import annotations

import asyncio
import hmac
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from faster_whisper import WhisperModel


MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3-turbo")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "fa")
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
VAD_FILTER = os.getenv("WHISPER_VAD_FILTER", "true").lower() in {"1", "true", "yes"}
MAX_CONCURRENT = max(1, int(os.getenv("WHISPER_MAX_CONCURRENT", "1")))
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(200 * 1024 * 1024)))
MODEL_CACHE = os.getenv("HF_HOME", "/models/huggingface")
ENGINE_API_KEY = os.getenv("ENGINE_API_KEY", "")

model: WhisperModel | None = None
gpu_slots = asyncio.Semaphore(MAX_CONCURRENT)


def load_model() -> WhisperModel:
    return WhisperModel(
        MODEL_NAME,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        download_root=MODEL_CACHE,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    global model
    model = await asyncio.to_thread(load_model)
    yield
    model = None


app = FastAPI(
    title="Private Whisper Large GPU Engine",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


def require_engine_key(authorization: str | None = Header(default=None)) -> None:
    if not ENGINE_API_KEY:
        return
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not hmac.compare_digest(supplied, ENGINE_API_KEY):
        raise HTTPException(401, "invalid engine API key")


def timestamp(seconds: float, decimal: str) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal}{millis:03d}"


def render_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n{timestamp(segment['start'], ',')} --> {timestamp(segment['end'], ',')}\n"
            f"{segment['text'].strip()}"
        )
    return "\n\n".join(blocks) + "\n"


def render_vtt(segments: list[dict[str, Any]]) -> str:
    cues = ["WEBVTT"]
    for segment in segments:
        cues.append(
            f"{timestamp(segment['start'], '.')} --> {timestamp(segment['end'], '.')}\n"
            f"{segment['text'].strip()}"
        )
    return "\n\n".join(cues) + "\n"


async def persist_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "audio.bin").suffix[:12]
    descriptor, raw_path = tempfile.mkstemp(prefix="stt-", suffix=suffix)
    path = Path(raw_path)
    total = 0
    try:
        with os.fdopen(descriptor, "wb") as target:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_AUDIO_BYTES:
                    raise HTTPException(413, "audio file is too large")
                target.write(chunk)
        if total == 0:
            raise HTTPException(400, "audio file is empty")
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def transcribe_sync(
    path: Path,
    language: str,
    prompt: str,
    temperature: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if model is None:
        raise RuntimeError("model is not loaded")
    generated, info = model.transcribe(
        str(path),
        language=language or None,
        beam_size=BEAM_SIZE,
        vad_filter=VAD_FILTER,
        initial_prompt=prompt or None,
        temperature=temperature,
        word_timestamps=False,
    )
    segments = [
        {
            "id": item.id,
            "start": item.start,
            "end": item.end,
            "text": item.text,
            "tokens": list(getattr(item, "tokens", []) or []),
        }
        for item in generated
    ]
    metadata = {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "duration_after_vad": getattr(info, "duration_after_vad", info.duration),
    }
    return segments, metadata


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": model is not None,
        "model": MODEL_NAME,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "max_concurrent": MAX_CONCURRENT,
    }


@app.post("/v1/audio/transcriptions", dependencies=[Depends(require_engine_key)])
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form(DEFAULT_LANGUAGE),
    response_format: str = Form("json"),
    prompt: str = Form(""),
    temperature: float = Form(0.0),
) -> Response:
    if response_format not in {"json", "verbose_json", "text", "srt", "vtt"}:
        raise HTTPException(400, "unsupported response format")
    path = await persist_upload(file)
    try:
        async with gpu_slots:
            segments, metadata = await asyncio.to_thread(
                transcribe_sync,
                path,
                language,
                prompt[:2000],
                temperature,
            )
    finally:
        path.unlink(missing_ok=True)

    text = "".join(segment["text"] for segment in segments).strip()
    if response_format == "text":
        return PlainTextResponse(text)
    if response_format == "srt":
        return PlainTextResponse(render_srt(segments), media_type="application/x-subrip")
    if response_format == "vtt":
        return PlainTextResponse(render_vtt(segments), media_type="text/vtt")
    if response_format == "verbose_json":
        return JSONResponse({"text": text, **metadata, "segments": segments})
    return JSONResponse({"text": text})
