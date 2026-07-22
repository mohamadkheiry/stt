from __future__ import annotations

import os
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import BinaryIO

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
ENGINE_URL = os.getenv("ENGINE_URL", "http://whisper-engine:8091").rstrip("/")
ENGINE_API_KEY = os.getenv("ENGINE_API_KEY", "")
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(200 * 1024 * 1024)))
TRANSCRIPTION_TAG = "تبدیل صوت به متن"

app = FastAPI(
    title="Whisper Large Persian Speech-to-Text API",
    version="1.0.0",
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
        data = {
            "language": language or "fa",
            "response_format": response_format,
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
    return Response(
        upstream.content,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={"X-STT-Engine": "whisper-large", "Cache-Control": "no-store"},
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


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


@app.post(
    "/api/transcribe",
    tags=[TRANSCRIPTION_TAG],
    summary="تبدیل فایل صوتی به متن",
    responses=TRANSCRIPTION_RESPONSES,
)
@app.post(
    "/v1/audio/transcriptions",
    tags=[TRANSCRIPTION_TAG],
    summary="OpenAI-compatible transcription",
    responses=TRANSCRIPTION_RESPONSES,
)
async def transcribe(
    file: UploadFile = File(..., description="فایل WAV، MP3، M4A، OGG، WebM یا فرمت صوتی رایج"),
    language: str = Form("fa", description="کد زبان؛ برای فارسی fa"),
    response_format: str = Form("json", description="json، text، verbose_json، srt یا vtt"),
    prompt: str = Form("", description="واژه‌های تخصصی یا متن راهنمای اختیاری"),
    temperature: float = Form(0.0, description="برای خروجی پایدار مقدار صفر پیشنهاد می‌شود"),
) -> Response:
    return await forward_transcription(file, language, response_format, prompt, temperature)
