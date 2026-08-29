# Thati AI

Evidence-first Myanmar fraud screening. Paste a message, get quoted evidence, identifiers, and safe next actions.

## Stack

- Python 3.12, FastAPI
- SQLite (path via `SQLITE_PATH`)
- Plain HTML/CSS/JavaScript in `web/`
- One Docker container
- Mock screening by default; live text analysis via the Google Gen AI SDK (`google-genai`)

## Configuration

Copy `.env.example` to `.env`. Defaults:

- `APP_MODE=mock` (use `live` only with a server-side `GEMINI_API_KEY`)
- `SQLITE_PATH=data/thati.db` locally, `/data/thati.db` in Docker
- `GEMINI_MODEL=gemini-3.7-flash`
- `GEMINI_TIMEOUT_MS=20000`
- `TRANSCRIPTION_MODEL=gemini-3.5-transcribe`

Do not commit API keys. The key is never sent to the browser.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/run_dev.sh
```

- App: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health
- Analyze text: `POST /api/analyze/text` with `{"text": "..."}`

## Tests

```bash
pytest -q
```

## Docker

```bash
docker compose up --build
```

SQLite is stored at `/data/thati.db` inside the container.
