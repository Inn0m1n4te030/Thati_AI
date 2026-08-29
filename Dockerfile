FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --user-group --shell /bin/false thati

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=thati:thati thati ./thati
COPY --chown=thati:thati web ./web

RUN mkdir -p /data \
    && chown thati:thati /data /app

USER thati

ENV APP_MODE=mock \
    SQLITE_PATH=/data/thati.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "thati.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
