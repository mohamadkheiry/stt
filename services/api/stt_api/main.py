from __future__ import annotations

import math
import os
import time
import uuid
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, Literal

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


ROOT = Path(__file__).resolve().parent
ENGINE_URL = os.getenv("ENGINE_URL", "http://whisper-engine:8091").rstrip("/")
ENGINE_API_KEY = os.getenv("ENGINE_API_KEY", "")
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(200 * 1024 * 1024)))
TRANSCRIPTION_TAG = "تبدیل صوت به متن"
OPENAI_MODEL = "whisper-1"
LOCAL_MODEL = "whisper-large-v3-turbo-q5-cuda"
MODEL_ALIASES = {OPENAI_MODEL, LOCAL_MODEL, "whisper-large-v3-turbo"}


class DurationUsage(BaseModel):
    type: Literal["duration"] = "duration"
    seconds: int


class WhisperTokenUsage(BaseModel):
    output_tokens: int
    source: Literal["whisper_decoder_token_ids"] = "whisper_decoder_token_ids"


class TranscriptionResponse(BaseModel):
    text: str
    usage: DurationUsage
    token_usage: WhisperTokenUsage
    tokens_consumed: int
    processing_status: Literal["completed"]
    error_code: str | None
    error_message: str | None
    processing_time_ms: int


class ErrorDetail(BaseModel):
    message: str
    type: str
    param: str | None
    code: str | None


class ContractErrorResponse(BaseModel):
    error: ErrorDetail
    tokens_consumed: int
    processing_status: Literal["failed"]
    error_code: str
    error_message: str
    processing_time_ms: int

app = FastAPI(
    title="Whisper Large Persian Speech-to-Text API",
    version="1.4.1",
    description=(
        "سرویس تبدیل فایل صوتی به متن با Whisper Large و شتاب‌دهی GPU. "
        "در Swagger روی **Try it out** بزنید، فایل را انتخاب کنید و پاسخ را دریافت کنید."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": TRANSCRIPTION_TAG,
            "description": "بارگذاری فایل صوتی و دریافت متن؛ سازگار با OpenAI Transcriptions API.",
        },
        {"name": "سلامت سرویس", "description": "بررسی آمادگی API و موتور GPU."},
    ],
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "defaultModelsExpandDepth": -1,
    },
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def openai_error(message: str, error_type: str, param: str | None, code: str | None) -> dict[str, Any]:
    return {"error": {"message": message, "type": error_type, "param": param, "code": code}}


def duration_usage_fields(payload: dict[str, Any]) -> dict[str, Any]:
    duration = max(0.0, float(payload.get("duration", 0.0) or 0.0))
    if duration == 0.0:
        duration = max(
            (float(segment.get("end", 0.0) or 0.0) for segment in payload.get("segments", [])),
            default=0.0,
        )
    seconds = math.ceil(duration)
    return {
        "usage": {"type": "duration", "seconds": seconds},
        "tokens_consumed": seconds,
    }


@app.middleware("http")
async def openai_response_headers(request: Request, call_next):
    started = time.perf_counter()
    request.state.processing_started = started
    response = await call_next(request)
    if request.url.path.startswith("/v1/"):
        response.headers["x-request-id"] = f"req_{uuid.uuid4().hex}"
        response.headers["openai-processing-ms"] = str(round((time.perf_counter() - started) * 1000))
    return response


@app.exception_handler(HTTPException)
async def openai_http_error(request: Request, exc: HTTPException):
    if not request.url.path.startswith("/v1/"):
        return await http_exception_handler(request, exc)
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    error_type = "invalid_request_error" if 400 <= exc.status_code < 500 else "server_error"
    message = str(detail.get("message", "Request failed"))
    code = str(detail.get("code") or ("invalid_request_error" if 400 <= exc.status_code < 500 else "server_error"))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            **openai_error(message, str(detail.get("type", error_type)), detail.get("param"), detail.get("code")),
            "tokens_consumed": 0,
            "processing_status": "failed",
            "error_code": code,
            "error_message": message,
            "processing_time_ms": max(
                0,
                round((time.perf_counter() - getattr(request.state, "processing_started", time.perf_counter())) * 1000),
            ),
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def openai_validation_error(request: Request, exc: RequestValidationError):
    if not request.url.path.startswith("/v1/"):
        return await request_validation_exception_handler(request, exc)
    first = exc.errors()[0] if exc.errors() else {}
    location = first.get("loc", [])
    param = str(location[-1]) if location else None
    message = str(first.get("msg", "Invalid request"))
    code = "missing_required_parameter" if first.get("type") == "missing" else "invalid_value"
    return JSONResponse(
        status_code=400,
        content={
            **openai_error(message, "invalid_request_error", param, code),
            "tokens_consumed": 0,
            "processing_status": "failed",
            "error_code": code,
            "error_message": message,
            "processing_time_ms": max(
                0,
                round((time.perf_counter() - getattr(request.state, "processing_started", time.perf_counter())) * 1000),
            ),
        },
    )


def engine_headers() -> dict[str, str]:
    if not ENGINE_API_KEY:
        return {}
    return {"Authorization": f"Bearer {ENGINE_API_KEY}"}


async def copy_upload(file: UploadFile) -> tuple[BinaryIO, int]:
    target = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_AUDIO_BYTES:
            target.close()
            raise HTTPException(413, "حجم فایل از محدودیت مجاز بیشتر است.")
        target.write(chunk)
    if total == 0:
        target.close()
        raise HTTPException(400, "فایل صوتی خالی است.")
    target.seek(0)
    return target, total


async def forward_transcription(
    file: UploadFile,
    language: str,
    response_format: str,
    prompt: str,
    temperature: float,
) -> Response:
    processing_started = time.perf_counter()
    if response_format not in {"json", "verbose_json", "text", "srt", "vtt"}:
        raise HTTPException(400, "response_format must be json, verbose_json, text, srt or vtt")

    upload, _ = await copy_upload(file)
    try:
        files = {
            "file": (
                file.filename or "speech.webm",
                upload,
                file.content_type or "application/octet-stream",
            )
        }
        upstream_response_format = "verbose_json" if response_format in {"json", "verbose_json"} else response_format
        data = {
            "model": OPENAI_MODEL,
            "language": language or "fa",
            "response_format": upstream_response_format,
            "temperature": str(temperature),
        }
        if prompt:
            data["prompt"] = prompt[:2000]
        async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0, connect=10.0)) as client:
            upstream = await client.post(
                f"{ENGINE_URL}/v1/audio/transcriptions",
                files=files,
                data=data,
                headers=engine_headers(),
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"ارتباط با موتور Whisper ناموفق بود: {exc}") from exc
    finally:
        upload.close()

    if upstream.is_error:
        raise HTTPException(502, upstream.text[:2000])

    if response_format in {"json", "verbose_json"}:
        try:
            payload = upstream.json()
        except ValueError as exc:
            raise HTTPException(502, "Whisper engine returned invalid JSON.") from exc

        output_tokens = sum(
            len(segment.get("tokens", []))
            for segment in payload.get("segments", [])
            if isinstance(segment, dict) and isinstance(segment.get("tokens", []), list)
        )
        payload.update(duration_usage_fields(payload))
        payload["token_usage"] = {
            "output_tokens": output_tokens,
            "source": "whisper_decoder_token_ids",
        }
        payload["processing_status"] = "completed"
        payload["error_code"] = None
        payload["error_message"] = None
        payload["processing_time_ms"] = max(0, round((time.perf_counter() - processing_started) * 1000))
        if response_format == "json":
            payload = {
                "text": str(payload.get("text", "")),
                "usage": payload["usage"],
                "token_usage": payload["token_usage"],
                "tokens_consumed": payload["tokens_consumed"],
                "processing_status": payload["processing_status"],
                "error_code": payload["error_code"],
                "error_message": payload["error_message"],
                "processing_time_ms": payload["processing_time_ms"],
            }
        return JSONResponse(
            payload,
            headers={
                "X-STT-Engine": "whisper-large",
                "X-Usage-Audio-Seconds": str(payload["usage"]["seconds"]),
                "X-Whisper-Output-Tokens": str(output_tokens),
                "X-Processing-Status": "completed",
                "X-Processing-Time-Ms": str(payload["processing_time_ms"]),
                "Cache-Control": "no-store",
            },
        )

    return Response(
        upstream.content,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={
            "X-STT-Engine": "whisper-large",
            "X-Processing-Status": "completed",
            "X-Processing-Time-Ms": str(max(0, round((time.perf_counter() - processing_started) * 1000))),
            "Cache-Control": "no-store",
        },
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/doc", include_in_schema=False)
def doc_redirect() -> Response:
    return Response(status_code=307, headers={"Location": "/redoc"})


@app.get(
    "/health",
    tags=["سلامت سرویس"],
    summary="بررسی سلامت API و موتور GPU",
    response_model=None,
)
async def health() -> JSONResponse:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{ENGINE_URL}/health", headers=engine_headers())
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return JSONResponse({"ok": False, "engine": "unavailable", "error": str(exc)}, status_code=503)
    return JSONResponse(
        {
            "ok": True,
            "engine": "whisper-large-gpu",
            "model": response.json().get("model", "unknown"),
        }
    )


TRANSCRIPTION_RESPONSES = {
    200: {
        "description": "متن استخراج‌شده از فایل صوتی",
        "content": {"application/json": {"example": {"text": "سلام، این یک فایل آزمایشی است."}}},
    },
    400: {"description": "فایل یا پارامتر نامعتبر"},
    413: {"description": "حجم فایل بیشتر از محدودیت"},
    502: {"description": "خطا در موتور Whisper"},
}

TRANSCRIPTION_RESPONSES[200]["content"] = {
    "application/json": {
        "example": {
            "text": "transcribed text",
            "usage": {"type": "duration", "seconds": 2},
            "token_usage": {
                "output_tokens": 11,
                "source": "whisper_decoder_token_ids",
            },
            "tokens_consumed": 2,
            "processing_status": "completed",
            "error_code": None,
            "error_message": None,
            "processing_time_ms": 842,
        }
    },
    "text/plain": {},
    "application/x-subrip": {},
    "text/vtt": {},
}
for error_status in (400, 413, 502):
    TRANSCRIPTION_RESPONSES[error_status]["model"] = ContractErrorResponse
TRANSCRIPTION_RESPONSES[404] = {
    "description": "Model not found",
    "model": ContractErrorResponse,
}


@app.post(
    "/api/transcribe",
    tags=[TRANSCRIPTION_TAG],
    summary="تبدیل فایل صوتی به متن (سازگار با نسخه قبلی)",
    responses=TRANSCRIPTION_RESPONSES,
    deprecated=True,
)
async def legacy_transcribe(
    file: UploadFile = File(..., description="فایل WAV، MP3، M4A، OGG، WebM یا فرمت صوتی رایج"),
    language: str = Form("fa", description="کد زبان؛ برای فارسی fa"),
    response_format: str = Form("json", description="json، text، verbose_json، srt یا vtt"),
    prompt: str = Form("", description="واژه‌های تخصصی یا متن راهنمای اختیاری"),
    temperature: float = Form(0.0, description="برای خروجی پایدار مقدار صفر پیشنهاد می‌شود"),
) -> Response:
    return await forward_transcription(file, language, response_format, prompt, temperature)


@app.get("/v1/models", tags=["OpenAI compatibility"], summary="List models")
def openai_models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": OPENAI_MODEL, "object": "model", "created": 0, "owned_by": "local"}],
    }


@app.get("/v1/models/{model}", tags=["OpenAI compatibility"], summary="Retrieve model")
def openai_model(model: str) -> dict[str, Any]:
    if model not in MODEL_ALIASES:
        raise HTTPException(
            404,
            {"message": f"The model '{model}' does not exist.", "param": "model", "code": "model_not_found"},
        )
    return {"id": OPENAI_MODEL, "object": "model", "created": 0, "owned_by": "local"}


@app.post(
    "/v1/audio/transcriptions",
    response_model=TranscriptionResponse,
    tags=["OpenAI compatibility"],
    summary="Create transcription",
    description="OpenAI-compatible multipart transcription endpoint. Use model=whisper-1.",
    responses=TRANSCRIPTION_RESPONSES,
)
async def openai_transcribe(
    file: UploadFile = File(..., description="FLAC, MP3, MP4, MPEG, MPGA, M4A, OGG, WAV or WebM audio"),
    model: str = Form(..., description="Model ID; use whisper-1"),
    language: str | None = Form(None, description="Optional ISO-639-1 language code"),
    prompt: str | None = Form(None, description="Optional vocabulary or style guide"),
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Form("json"),
    temperature: float = Form(0.0, ge=0.0, le=1.0),
    timestamp_granularities: list[Literal["word", "segment"]] | None = Form(
        None,
        alias="timestamp_granularities[]",
    ),
    stream: bool = Form(False, description="Ignored for whisper-1"),
) -> Response:
    if model not in MODEL_ALIASES:
        raise HTTPException(
            404,
            {"message": f"The model '{model}' does not exist.", "param": "model", "code": "model_not_found"},
        )
    if timestamp_granularities and response_format != "verbose_json":
        raise HTTPException(
            400,
            {
                "message": "timestamp_granularities[] requires response_format=verbose_json.",
                "param": "timestamp_granularities[]",
                "code": "invalid_value",
            },
        )
    _ = stream
    return await forward_transcription(
        file,
        language or "fa",
        response_format,
        prompt or "",
        temperature,
    )
