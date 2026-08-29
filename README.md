# Thati AI

Evidence-first Myanmar fraud screening. Paste a message, get quoted evidence, identifiers, and safe next actions.

## Stack

- Python 3.12, FastAPI, one Uvicorn worker (SQLite)
- SQLite on a persistent volume at `/data/thati.db` in Docker
- Plain HTML/CSS/JavaScript in `web/`
- One Docker image (FastAPI, static frontend, FFmpeg), non-root
- Mock screening by default; live analysis needs a server-side `GEMINI_API_KEY`

Do not commit API keys, `.env`, SQLite files, uploads, or test caches. The Gemini key is never sent to the browser.

## Configuration

Copy placeholders only:

```bash
cp .env.example .env
```

Then edit `.env` on the server. Empty `GEMINI_API_KEY` and `ADMIN_TOKEN` in `.env.example` are placeholders — put real values only in `.env` (gitignored).

| Variable | Mock | Live |
| --- | --- | --- |
| `APP_MODE` | `mock` | `live` |
| `GEMINI_API_KEY` | leave empty | server-side Gemini key |
| `ADMIN_TOKEN` | long random token | same |
| `SQLITE_PATH` | `/data/thati.db` in Docker | same |

Local venv (not Docker) may use `SQLITE_PATH=data/thati.db`. Docker Compose always mounts SQLite at `/data/thati.db`.

## Docker on an Azure Ubuntu VPS (port 80)

Install Docker Engine and the Compose plugin, then from the repo directory:

### Mock

```bash
cp .env.example .env
# Set ADMIN_TOKEN in .env. Leave APP_MODE=mock and GEMINI_API_KEY empty.
docker compose up --build -d
curl -sS http://127.0.0.1/health
```

Public UI: `http://<server>/`  
Admin (not linked from the public page): `http://<server>/admin`  
Health: `http://<server>/health`

### Live

```bash
cp .env.example .env
# In .env set:
#   APP_MODE=live
#   GEMINI_API_KEY=<server-side key>
#   ADMIN_TOKEN=<long random token>
docker compose up --build -d
curl -sS http://127.0.0.1/health
```

Compose maps host port **80** to the app on **8000**. SQLite is stored in the named volume `thati-data` at `/data`. Stop without deleting data: `docker compose down`. Wipe the database volume: `docker compose down -v`.

## Local development (venv)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# For local venv, set SQLITE_PATH=data/thati.db and APP_MODE=mock
python3 -m uvicorn thati.main:app --reload --host 127.0.0.1 --port 8000
```

- App: http://127.0.0.1:8000/
- Health: http://127.0.0.1:8000/health
- Analyze text: `POST /api/analyze/text` with `{"text": "..."}`

## Tests

```bash
pytest -q
```
