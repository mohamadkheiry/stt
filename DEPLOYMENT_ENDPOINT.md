# Latest published deployment

This file records the latest verified deployment address for operators and developers. Update it in the same pull request whenever the service host, port, protocol, or route changes.

## Current endpoint

| Field | Value |
|---|---|
| Environment | Production LAN |
| Host | `192.168.20.189` |
| Protocol | `http` |
| Published port | `8101` |
| Base URL | <http://192.168.20.189:8101/> |
| Upload UI | <http://192.168.20.189:8101/> |
| Swagger | <http://192.168.20.189:8101/docs> |
| ReDoc | <http://192.168.20.189:8101/redoc> |
| Health | <http://192.168.20.189:8101/health> |
| Transcription API | `POST http://192.168.20.189:8101/v1/audio/transcriptions` |
| Simple dashboard API | `POST http://192.168.20.189:8101/api/transcribe` |
| API version | `1.4.1` |
| Usage reporting | OpenAI duration `usage` + exact Whisper decoder `token_usage` |
| Last verified | `2026-07-26` |

The engine endpoint `127.0.0.1:8091` is internal to the server and must not be published to users.

## Current runtime status

- Engine container: `ai-whisper-asr-engine`
- API/Swagger container: `ai-persian-asr-studio`
- Both containers use `restart: always`.
- Both containers were healthy at the last verification.
- A real transcription verified `usage.seconds`, `token_usage.output_tokens`, and the matching usage headers.
- Success and validation-error tests verified all required audit contract fields.
- A real transcription verified `tokens_consumed == usage.seconds` while preserving all other contract fields.
- Boot supervisor: `ai-platform-compose.service`
- GPU discovery at boot: `nvidia-cdi-refresh.path`

## Security scope

`192.168.20.189` is a private LAN address. It is intentionally recorded because this repository is the operational source of truth requested by the owner. Do not publish credentials, API keys, SSH passwords, or public-server addresses in this file.

## Update checklist

When deploying to a new address:

1. Update the host, port, protocol, routes, and verification date above.
2. Confirm `/health` returns HTTP 200 from another machine on the intended network.
3. Submit a real audio file through `/v1/audio/transcriptions`.
4. Confirm the engine and API containers are healthy and use `restart: always`.
5. Confirm the Compose systemd unit is enabled and active.
6. Commit this file together with the deployment change.
