FROM nvidia/cuda:12.9.2-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl libgomp1 python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/engine/requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install --requirement requirements.txt
COPY services/engine/stt_engine ./stt_engine

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /models \
    && chown -R appuser:appuser /app /models
USER appuser

EXPOSE 8091
CMD ["sh", "-c", "uvicorn stt_engine.main:app --host 0.0.0.0 --port ${PORT:-8091} --proxy-headers"]
