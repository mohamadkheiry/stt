# OpenAI API compatibility

The public API works with OpenAI-compatible clients while inference remains fully local.

## Contract

- Base URL: `http://<server>:8101/v1`
- Models: `GET /v1/models`
- Transcription: `POST /v1/audio/transcriptions`
- Multipart required fields: `file` and `model`
- Local OpenAI-compatible model ID: `whisper-1`
- Default JSON response includes `text`, OpenAI-compatible duration `usage`, and exact local decoder `token_usage`.
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

## Usage reporting

OpenAI's `whisper-1` contract reports usage by input audio duration rather than
inventing input token counts. JSON responses therefore contain:

```json
{
  "usage": {"type": "duration", "seconds": 9},
  "token_usage": {
    "output_tokens": 42,
    "source": "whisper_decoder_token_ids"
  }
}
```

The local extension `token_usage.output_tokens` is an exact count of token IDs
emitted by the Whisper decoder. It is available for `json` and `verbose_json`.
Plain text and subtitle formats remain byte-compatible and do not embed JSON
usage metadata.

## Audit fields

The JSON contract requires `tokens_consumed`, `processing_status`,
`error_code`, `error_message`, and `processing_time_ms`. Successful responses
use `completed` with null error fields. OpenAI-style error responses keep the
nested `error` object and additionally expose the audit fields with status
`failed` and zero consumed tokens.

For successful transcriptions, `tokens_consumed` is exactly equal to
`usage.seconds`, which is the decoded audio duration rounded upward with
`ceil`. `usage`, `token_usage`, processing status, error fields, and processing
time retain their existing structures and semantics.

## Downstream services

Internal consumers must send `model=whisper-1` and should parse the OpenAI error envelope before falling back to raw response text. Any future breaking contract change requires a new versioned route rather than changing `/v1/*` in place.
