# API reference

Interactive documentation is available at `/docs`; ReDoc is available at `/redoc`.

## `POST /v1/audio/transcriptions`

OpenAI-compatible multipart endpoint. `/api/transcribe` remains as a deprecated backwards-compatible route.

| Field | Required | Default | Description |
|---|---:|---|---|
| `file` | yes | — | WAV, MP3, M4A, OGG, WebM, MP4, or another PyAV-supported input |
| `model` | yes | — | Use the OpenAI-compatible model ID `whisper-1` |
| `language` | no | `fa` | ISO language code; use an empty value for automatic detection |
| `response_format` | no | `json` | `json`, `verbose_json`, `text`, `srt`, or `vtt` |
| `prompt` | no | empty | Initial prompt or domain vocabulary, limited to 2,000 characters |
| `temperature` | no | `0` | Decoder temperature |

### JSON

```bash
curl -F "file=@sample.wav" \
  -F "model=whisper-1" \
  -F "language=fa" \
  -F "response_format=json" \
  http://localhost:8101/v1/audio/transcriptions
```

```json
{"text":"سلام، این یک فایل آزمایشی است."}
```

### Usage fields

JSON responses include OpenAI-compatible duration usage for `whisper-1` and
the exact number of decoder token IDs emitted by the local Whisper engine:

```json
{
  "text": "transcribed text",
  "usage": {"type": "duration", "seconds": 2},
  "token_usage": {
    "output_tokens": 11,
    "source": "whisper_decoder_token_ids"
  },
  "tokens_consumed": 11,
  "processing_status": "completed",
  "error_code": null,
  "error_message": null,
  "processing_time_ms": 842
}
```

`usage.seconds` is rounded up to a whole second, matching the OpenAI duration
usage contract for duration-billed transcription models.
`token_usage.output_tokens` is counted from actual Whisper decoder token IDs;
it is not estimated from text length. Whisper audio input is duration-based,
so this API does not invent an input token count.

### Audit contract

All JSON transcription responses expose the following required top-level
fields:

| Field | Success | Failure | Meaning |
|---|---|---|---|
| `tokens_consumed` | Exact decoder token count | `0` | Tokens emitted before completion/failure |
| `processing_status` | `completed` | `failed` | Final processing state |
| `error_code` | `null` | Stable string code | Machine-readable failure code |
| `error_message` | `null` | Error description | Human-readable failure reason |
| `processing_time_ms` | Integer | Integer | Server processing time in milliseconds |

Failures preserve the OpenAI `error` envelope and include the audit fields at
the top level. Plain text and subtitle outputs cannot embed JSON fields; their
successful processing status and elapsed time are exposed through HTTP headers.

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
  -F "model=whisper-1" \
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

## OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8101/v1", api_key="local-not-required")
with open("sample.wav", "rb") as audio:
    result = client.audio.transcriptions.create(model="whisper-1", file=audio, language="fa")
print(result.text)
```

## Errors

All `/v1/*` failures use the OpenAI error envelope:

```json
{"error":{"message":"...","type":"invalid_request_error","param":"model","code":"model_not_found"}}
```

| Status | Meaning |
|---:|---|
| 400 | Empty upload or unsupported response format |
| 413 | Upload exceeds `MAX_AUDIO_BYTES` |
| 400 | Missing field or invalid multipart input |
| 502 | Engine connection or inference error |
| 503 | Health check cannot reach a ready engine |
