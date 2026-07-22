# Deployment

## GPU prerequisites

Install Docker Engine, Docker Compose, a compatible NVIDIA driver, and NVIDIA Container Toolkit. Confirm that a CUDA container can see the GPU before starting this project.

## Standard deployment

```bash
git clone https://github.com/mohamadkheiry/stt.git /opt/whisper-stt
cd /opt/whisper-stt
cp .env.example .env
```

Generate a strong internal key and place it in `.env`:

```bash
openssl rand -hex 32
```

Build and start:

```bash
docker compose up -d --build
docker compose ps
```

## NVIDIA CDI

On a host that exposes `nvidia.com/gpu` CDI devices:

```bash
docker compose -f compose.yaml -f compose.cdi.yaml up -d --build
```

## Start after reboot

Both containers use `restart: always`. For explicit stack-level boot ordering, install the included systemd unit:

```bash
sudo cp deploy/systemd/whisper-stt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now whisper-stt.service
```

Change `WorkingDirectory` in the unit if the repository is not located at `/opt/whisper-stt`.

## Reverse proxy

Before internet exposure, place port 8101 behind a reverse proxy that provides TLS, request-size limits, timeouts appropriate for long audio, and user authentication. Do not publish engine port 8091.

## Upgrade

```bash
cd /opt/whisper-stt
git pull --ff-only
docker compose build --pull
docker compose up -d
curl -fsS http://127.0.0.1:8101/health
```

Keep the previous image until the health check and a real transcription pass.
