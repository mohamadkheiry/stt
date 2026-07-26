# Development guide

## Local API tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.txt pytest
pytest -q
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## CPU smoke stack

The CPU override removes the GPU reservation and uses the `small` model:

```bash
cp .env.example .env
docker compose -f compose.yaml -f compose.cpu.yaml up -d --build
```

This mode validates the contract and UI; it is not representative of Large-model production performance.

## Code ownership boundaries

- Keep public request validation and UI behavior in `services/api`.
- Keep model loading, decoding, VAD, and output rendering in `services/engine`.
- Preserve `/v1/audio/transcriptions` when replacing an engine.
- Add new environment variables to `.env.example` and the appropriate document.
- Never commit `.env`, model weights, user audio, transcripts containing private data, or access tokens.

## Validation before a pull request

```bash
python -m compileall -q services tests
pytest -q
cp .env.example .env
docker compose config --quiet
```

For inference changes, also build the images and run one real Persian transcription on a CUDA host.
