# Thati AI

Evidence-first Myanmar fraud screening. This repository currently contains the **application scaffold only** — fraud analysis is not implemented yet.

## Stack

- Python 3.12, FastAPI
- SQLite (path via `SQLITE_PATH`)
- Plain HTML/CSS/JavaScript in `web/`
- One Docker container

## Configuration

Copy `.env.example` to `.env`. Defaults:

- `APP_MODE=mock`
- `SQLITE_PATH=data/thati.db` locally, `/data/thati.db` in Docker
- `GEMINI_MODEL=gemini-3.7-flash`
- `TRANSCRIPTION_MODEL=gemini-3.5-transcribe`

Do not commit API keys.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/run_dev.sh
```

- App: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health

## Tests

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```

SQLite is stored at `/data/thati.db` inside the container.
