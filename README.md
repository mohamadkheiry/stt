# Whisper Large Persian STT

Production-oriented speech-to-text service with a Persian upload UI, Swagger/OpenAPI, an OpenAI-compatible transcription endpoint, and a GPU-backed Whisper Large engine.

[راهنمای فارسی](README.fa.md) · [Architecture](docs/architecture.md) · [API](docs/api.md) · [OpenAI compatibility](docs/openai-compatibility.md) · [Deployment](docs/deployment.md) · [Operations](docs/operations.md) · [Development](docs/development.md)

## Features

- Whisper `large-v3-turbo` through `faster-whisper` and CUDA
- File upload UI and interactive Swagger at `/docs`
- OpenAI-compatible `POST /v1/audio/transcriptions`
- JSON, text, verbose JSON, SRT, and VTT output
- OpenAI-style duration `usage` plus exact Whisper decoder `token_usage` in JSON responses
- Audit fields for token consumption, processing status, errors, and processing time
- Docker health checks, bounded GPU concurrency, persistent model cache, restart policy, and log rotation
- Separate public API and private engine containers
- No credentials or model weights committed to Git

## Quick start

Prerequisites: Docker Engine, Docker Compose, an NVIDIA GPU, a compatible driver, and NVIDIA Container Toolkit.

```bash
cp .env.example .env
# Change ENGINE_API_KEY in .env before exposing the service.
docker compose up -d --build
docker compose ps
```

For an NVIDIA CDI host:

```bash
docker compose -f compose.yaml -f compose.cdi.yaml up -d --build
```

Open:

- Upload UI: <http://localhost:8101/>
- Swagger: <http://localhost:8101/docs>
- ReDoc: <http://localhost:8101/redoc>
- Health: <http://localhost:8101/health>

Example:

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

## Repository layout

```text
services/api/       Public FastAPI, Swagger, and upload UI
services/engine/    Private faster-whisper CUDA engine
tests/              API-contract tests
docs/               Architecture, API, deployment, operations, development
compose.yaml        Standard NVIDIA runtime deployment
compose.cdi.yaml    NVIDIA CDI override
```

## Security

The engine is available only on the private Compose network. The public API currently has no end-user authentication; put it behind an authenticated reverse proxy before exposing it outside a trusted LAN. `ENGINE_API_KEY` protects calls between the API and engine and must be changed in production.

## License

No license has been selected by the repository owner yet. Do not assume permission for redistribution beyond the repository's intended use until a license is added.
