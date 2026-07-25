# OpenAI API compatibility

The public API works with OpenAI-compatible clients while inference remains fully local.

## Contract

- Base URL: `http://<server>:8101/v1`
- Models: `GET /v1/models`
- Transcription: `POST /v1/audio/transcriptions`
- Multipart required fields: `file` and `model`
- Local OpenAI-compatible model ID: `whisper-1`
- Default JSON response: `{"text":"..."}`
- Every `/v1/*` response includes `x-request-id`.
- Every `/v1/*` error uses `{"error":{"message", "type", "param", "code"}}`.

The deprecated `POST /api/transcribe` route remains available during the backwards-compatibility period. New integrations must use `/v1/audio/transcriptions`.

## Supported response formats

- `json`
- `text`
- `verbose_json`
- `srt`
- `vtt`

`timestamp_granularities[]` is accepted only with `response_format=verbose_json`. `stream` is accepted and ignored for `whisper-1`, matching OpenAI's Whisper behavior.

## Downstream services

Internal consumers must send `model=whisper-1` and should parse the OpenAI error envelope before falling back to raw response text. Any future breaking contract change requires a new versioned route rather than changing `/v1/*` in place.
