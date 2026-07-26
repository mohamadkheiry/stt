FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/api/requirements.txt ./requirements.txt
RUN pip install --requirement requirements.txt
COPY services/api/stt_api ./stt_api

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8101
CMD ["sh", "-c", "uvicorn stt_api.main:app --host 0.0.0.0 --port ${PORT:-8101} --proxy-headers"]
