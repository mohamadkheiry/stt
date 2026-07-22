# Operations and recovery

## Routine checks

```bash
docker compose ps
curl -fsS http://127.0.0.1:8101/health
nvidia-smi
```

## Logs

```bash
docker compose logs -f --tail=100 stt-api whisper-engine
```

Docker rotates each container's JSON logs at three files of 20 MB.

## Controlled restart

Restart only the API without unloading the GPU model:

```bash
docker compose restart stt-api
```

Restart the inference engine:

```bash
docker compose restart whisper-engine
```

## Capacity

`WHISPER_MAX_CONCURRENT=1` is the safe default. Increasing it can improve throughput but also increases VRAM pressure. Load-test representative audio while watching `nvidia-smi` before changing it. For predictable multi-user behavior, keep the engine concurrency bounded and queue excess requests at the API or reverse proxy.

## Model-cache backup

The cache can be downloaded again, so backup is optional. To archive it:

```bash
docker run --rm \
  -v whisper-stt_whisper-models:/source:ro \
  -v "$PWD":/backup \
  alpine tar -czf /backup/whisper-models.tar.gz -C /source .
```

Do not commit this archive to Git.

## Recovery checklist

1. Check `docker compose ps` and both container logs.
2. Confirm the GPU is visible with `nvidia-smi`.
3. Confirm free disk space for the model cache.
4. Restart only the failed component.
5. If the model cache is corrupt, move the volume aside and allow a clean download.
6. Verify health and submit a small known-good audio file.
