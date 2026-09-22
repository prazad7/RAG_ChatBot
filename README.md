# Hybrid RAG Chatbot

A document-QA chatbot combining dense (FAISS), sparse (BM25), and graph (Neo4j) retrieval,
with a cross-encoder reranker, NeMo Guardrails, and DeepEval/LangSmith scoring. FastAPI
backend, React/Vite frontend.

- **Backend**: FastAPI, LangChain, FAISS, Neo4j, OCR (Tesseract) — `backend/`
- **Frontend**: React + Vite dual-panel chat UI — `frontend/`
- **Graph store**: Neo4j (local Docker container or Neo4j Aura cloud)

## Quick start (Docker, recommended)

Brings up Neo4j, backend, and frontend together.

```bash
docker compose up --build
```

Open **http://localhost:5190** once all three containers report healthy. Log in with
`admin` / `password@123` (or whatever `APP_AUTH_USERNAME`/`APP_AUTH_PASSWORD` you set —
see [Configuration](#configuration)).

```bash
docker compose up --build -d   # detached
docker compose logs -f backend # tail one service's logs
docker compose down            # stop everything
docker compose down -v         # stop and wipe Neo4j/backend data volumes
```

Notes:
- The backend container waits for Neo4j to report healthy before starting, and the
  frontend waits for the backend, so a plain `docker compose up --build` brings the stack
  up in the right order on its own.
- The backend image installs `tesseract-ocr` and uses it via `PATH` — no `TESSERACT_CMD`
  needed inside Docker (the compose file blanks out the Windows path from `backend/.env`
  for this reason).
- `docker compose down -v` deletes the Neo4j database and all uploaded
  documents/sessions. Omit `-v` to keep that data across restarts.

## Quick start (local dev, no Docker for backend/frontend)

Runs Neo4j in Docker but the backend and frontend directly on your machine, with hot
reload. Useful when actively editing code.

### Prerequisites

- **Python 3.11** (not newer — some ML deps lag behind brand-new Python releases)
- **Node.js + npm** (any recent LTS)
- **Tesseract OCR** binary on your machine:
  ```
  winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
  ```
  Then set `TESSERACT_CMD` in `backend/.env` to the installed path (default:
  `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **Docker Desktop** (for the local Neo4j container) — or a Neo4j Aura cloud instance
  instead, see [Configuration](#configuration).

### Setup

```bash
# Neo4j
docker compose up -d neo4j

# Backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
copy backend\.env.example backend\.env    # then fill in real values, see below

# Frontend
cd frontend
npm install
copy .env.example .env                    # default is fine for local dev
cd ..
```

### Run

```bash
# Terminal 1 - backend
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8600

# Terminal 2 - frontend
cd frontend
npm run dev
```

Open **http://127.0.0.1:5190**. Ctrl-C both terminals to stop; `docker compose stop neo4j`
to stop the database.

## Configuration
All backend config lives in `backend/.env` (copy from `backend/.env.example`). Required:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Chat + embeddings model calls |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | Graph store connection. For the local Docker Neo4j: `bolt://localhost:7687` / `neo4j` / `ragchatbot123` / `neo4j`. For Aura: use the connection URI Aura gives you, and note the database is *not* named `neo4j` — run `SHOW DATABASES` against the `system` database to find its real name. |
| `APP_AUTH_USERNAME` / `APP_AUTH_PASSWORD` | Login credentials for the app itself |
| `JWT_SECRET_KEY` | Session token signing — set to a real random value outside local dev |
| `TESSERACT_CMD` | Path to `tesseract.exe` (Windows local dev only — blank/unset on Linux/Docker, where it's on `PATH`) |

Optional: `LANGCHAIN_API_KEY` (LangSmith tracing, no-ops if unset), `DEEPEVAL_ENABLED` /
`CONFIDENT_API_KEY` (answer-quality scoring).

`frontend/.env` (copy from `frontend/.env.example`) needs no changes for local dev —
`VITE_API_BASE_URL=http://localhost:8600` works whether the backend is running natively or
in Docker, since its port is published to the host either way. For a build served from
somewhere other than `localhost`, override it (Docker: pass `VITE_API_BASE_URL` as a build
arg, since Vite bakes `VITE_*` vars in at build time — see `docker-compose.yml`).

If Neo4j is unreachable, the backend still starts — graph search is just disabled
(`graph_search_available: false` in `/api/health`); dense/sparse retrieval still work.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | Log in, get a session token |
| `GET` | `/api/me` | Current session info |
| `DELETE` | `/api/me` | Log out |
| `POST` | `/api/upload` | Upload document(s) for ingestion |
| `POST` | `/api/chat` | Ask a question, get a grounded answer |
| `GET` | `/api/chat/{turn_id}/eval` | DeepEval relevancy/faithfulness scores for a turn |
| `GET` | `/api/health` | Liveness + `graph_search_available` flag |

## Testing / verifying it works

There's no separate pytest/vitest suite — the agent skill at
`.claude/skills/run-rag-chatbot/driver.mjs` is the end-to-end smoke test: it starts both
servers if needed, logs in, uploads a sample doc, asks a question, and screenshots the
result.

```bash
node .claude/skills/run-rag-chatbot/driver.mjs
```

## Troubleshooting

- **`ValueError: Could not connect to Neo4j database`** at backend startup: non-fatal,
  graph search is disabled for that process, everything else still works.
- **Backend container unhealthy / `/api/health` never responds**: check
  `docker compose logs backend` — most likely a missing/invalid `OPENAI_API_KEY`, or Neo4j
  not yet healthy (backend waits up to its `depends_on` healthcheck, but first-run model
  downloads can take a minute or two after that).
- **`curl: (7) Failed to connect`** right after starting a server: it needs a few seconds
  to bind — poll instead of a single immediate request.
- **(Local dev only) Windows Smart App Control blocks a freshly-installed native DLL**
  (seen with `torch`, `tiktoken`, `pyarrow`): a first-run reputation check, not a permanent
  block — retrying the same import after a short wait succeeds with no config change. This
  doesn't come up in the Docker path.
- **(Local dev only) `npm run dev` only reachable on `::1`, not `127.0.0.1`**: already
  fixed via `server.host: '127.0.0.1'` in `frontend/vite.config.js` — flagging in case that
  config ever changes.
- **A stale `session_token` in the browser survives a backend restart**: the session store
  is in-memory and resets on restart. The frontend clears storage and redirects to login on
  any 401/404, so just log in again.

## Deployment note

Not yet built/tested, but the app was designed to be Linux-portable: the Docker path above
uses the same `python:3.11-slim` + `apt-get install tesseract-ocr` approach a plain Ubuntu
VPS would need, and the Windows-specific Smart App Control / TLS-inspection gotchas don't
apply there.
