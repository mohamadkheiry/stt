# API reference

Interactive documentation is available at `/docs`; ReDoc is available at `/redoc`.

## `POST /v1/audio/transcriptions`

OpenAI-compatible multipart endpoint. `/api/transcribe` is an equivalent convenience route used by the web UI.

| Field | Required | Default | Description |
|---|---:|---|---|
| `file` | yes | — | WAV, MP3, M4A, OGG, WebM, MP4, or another PyAV-supported input |
| `language` | no | `fa` | ISO language code; use an empty value for automatic detection |
| `response_format` | no | `json` | `json`, `verbose_json`, `text`, `srt`, or `vtt` |
| `prompt` | no | empty | Initial prompt or domain vocabulary, limited to 2,000 characters |
| `temperature` | no | `0` | Decoder temperature |

### JSON

```bash
curl -F "file=@sample.wav" \
  -F "language=fa" \
  -F "response_format=json" \
  http://localhost:8101/v1/audio/transcriptions
```

```json
{"text":"سلام، این یک فایل آزمایشی است."}
```

### Verbose JSON

```json
{
  "text": "سلام",
  "language": "fa",
  "language_probability": 0.99,
  "duration": 2.4,
  "duration_after_vad": 1.8,
  "segments": [
    {"id": 0, "start": 0.0, "end": 1.8, "text": "سلام"}
  ]
}
```

### Subtitle output

```bash
curl -F "file=@meeting.mp3" \
  -F "language=fa" \
  -F "response_format=srt" \
  http://localhost:8101/v1/audio/transcriptions \
  --output meeting.srt
```

## `GET /health`

Returns HTTP 200 only when the public API can reach a loaded engine.

```json
{"ok":true,"engine":"whisper-large-gpu","model":"large-v3-turbo"}
```

## Errors

| Status | Meaning |
|---:|---|
| 400 | Empty upload or unsupported response format |
| 413 | Upload exceeds `MAX_AUDIO_BYTES` |
| 422 | Missing field or invalid multipart input |
| 502 | Engine connection or inference error |
| 503 | Health check cannot reach a ready engine |
