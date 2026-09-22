---
name: run-rag-chatbot
description: Build, run, and drive the Hybrid RAG Chatbot (FastAPI backend + React frontend). Use when asked to start the app, run it, test the RAG pipeline, take a screenshot of its UI, or verify a change works end-to-end.
---

A FastAPI backend (hybrid dense/sparse/graph RAG pipeline) plus a React/Vite dual-panel
chat UI. Drive it via the headless Playwright driver at
`.claude/skills/run-rag-chatbot/driver.mjs` — it starts both servers if needed, logs in,
uploads a sample doc, asks a question, and screenshots the result. This is a web app; the
driver is the harness (no `chromium-cli` binary is installed in this environment, so a
self-contained Playwright script was built instead — see Gotchas).

All paths below are relative to the repo root (`RAG_ChatBot/`) unless stated otherwise.

## Prerequisites

Verified on **Windows** (this project was built and run on Windows, not Ubuntu — see the
VPS note at the bottom for the Linux/Hostinger deployment path).

- **Python 3.11** (not 3.14 — several ML deps lag behind brand-new Python releases; a 3.14
  venv here produced no functional issues we hit, but 3.11 is the version this was built
  and tested against). On this machine: `C:\Users\<you>\AppData\Local\Programs\Python\Python311\python.exe`.
- **Node.js + npm** (any recent LTS; built against Node 24 / npm 11 here).
- **Tesseract OCR binary** (for the OCR-on-embedded-images requirement). Installed with:
  ```
  winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
  ```
  Installs to `C:\Program Files\Tesseract-OCR\tesseract.exe` — set `TESSERACT_CMD` in
  `backend/.env` to that path. (`choco install tesseract` also works but needs an elevated
  shell; winget's default-scope install does not.)
- **Neo4j** — either a Neo4j Aura Free instance (cloud) or a local Docker container. A
  `docker-compose.yml` at the repo root starts a local one:
  ```
  docker compose up -d
  ```
  (neo4j:5.24-community, bolt on 7687, browser on 7474, credentials `neo4j`/`ragchatbot123`).
  Graph search degrades gracefully (logs a warning, `graph_search_available: false` in
  `/api/health`) if Neo4j is unreachable — the rest of the app still works.

## Setup

```bash
# Backend
"C:\<path-to-python311>\python.exe" -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Driver (this skill's own harness dependencies)
cd .claude/skills/run-rag-chatbot && npm install && npx playwright install chromium && cd ../../..
```

Copy `backend/.env.example` to `backend/.env` and fill in real values — required:
`OPENAI_API_KEY`, `NEO4J_URI`/`NEO4J_USERNAME`/`NEO4J_PASSWORD`/`NEO4J_DATABASE` (see
Gotchas for both Neo4j pitfalls we hit), `LANGCHAIN_API_KEY` (optional — LangSmith tracing
just no-ops without it). Copy `frontend/.env.example` to `frontend/.env` (default
`VITE_API_BASE_URL=http://localhost:8600` needs no changes for local dev).

No build step — the backend runs directly from source and the frontend is served by Vite's
dev server (no `npm run build` needed for local use).

## Run (agent path)

```bash
node .claude/skills/run-rag-chatbot/driver.mjs
```

This single command is the whole loop: it checks whether the backend (`:8600`) and
frontend (`:5190`) are already up and starts whichever isn't (backend via the venv's
uvicorn, frontend via `npm run dev`), then drives a real headless Chromium through
login → upload `.claude/skills/run-rag-chatbot/sample_docs/sample_report.txt` → ask a
question → wait for the grounded/ungrounded badge → screenshot → check console errors.
Exits non-zero (and saves `screenshots/failure.png`) if anything breaks.

Screenshots land in `.claude/skills/run-rag-chatbot/screenshots/` (`smoke.png` on success,
`failure.png` on error). Logs from a driver-launched backend/frontend aren't captured
separately — if you need them, launch the servers yourself first (see below) so their
stdout stays visible, then run the driver against the already-running servers.

For manual API-level poking instead of the UI, once the backend is up:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8600/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password@123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session_token'])")
curl -s -X POST http://127.0.0.1:8600/api/upload -H "Authorization: Bearer $TOKEN" \
  -F "files=@.claude/skills/run-rag-chatbot/sample_docs/sample_report.txt"
curl -s -X POST http://127.0.0.1:8600/api/chat -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"message":"What was the Q3 net profit?"}'
```

## Run (human path)

```bash
# Terminal 1 - backend
cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8600

# Terminal 2 - frontend
cd frontend && npm run dev
```

Open `http://127.0.0.1:5190` (note: plain `npm run dev` defaults to port 5173 and to the
IPv6 loopback only — this repo's `frontend/vite.config.js` pins it to `127.0.0.1:5190`;
see Gotchas for why). Log in with `admin` / `password@123`. Ctrl-C both terminals to stop.

## Test

There is no separate automated test suite (pytest/vitest) in this repo — `driver.mjs` *is*
the end-to-end test. Run it after any change to backend or frontend code to confirm the
full pipeline (ingestion → hybrid retrieval → guardrails → generation → UI rendering)
still works.

---

## Gotchas

- **Ports 8000 and 5173 are already taken on this machine** by unrelated Docker containers
  (`video_content-backend`, `video_content-frontend`) — curling those ports gets a
  different app's 404, not "connection refused", which is confusing. This repo's backend
  uses `8600` and frontend uses `5190` specifically to avoid this.
- **`npm run dev` binds to `::1` (IPv6) only** on this machine by default, so
  `curl http://127.0.0.1:5173` hangs/fails even though the dev server is genuinely running.
  Fixed here via `server.host: '127.0.0.1'` in `vite.config.js`. If you see a Vite process
  running (`node .../vite/bin/vite.js` in `Get-CimInstance Win32_Process`) but can't reach
  it, this is why.
- **Windows Smart App Control can block freshly-`pip install`ed native DLLs** (we hit this
  with `torch`, `tiktoken`, and `pyarrow`'s `_dataset` extension — error: "An Application
  Control policy has blocked this file"). It's a first-run reputation check, not a
  permanent block: retrying the same import a few seconds/minutes later succeeds without
  any config change. Don't disable Smart App Control to fix this — it's one-way on
  Windows 11 (can't be re-enabled without a reinstall) and the block resolves itself.
- **`sentence-transformers`'s `CrossEncoder` transitively imports `datasets` → `pyarrow.dataset`**,
  and that specific `pyarrow` native extension stayed blocked by Smart App Control far
  longer than `torch`/`tiktoken` did in testing. The reranker in this repo
  (`backend/app/retrieval/reranker.py`) therefore loads `cross-encoder/ms-marco-MiniLM-L-6-v2`
  directly via `transformers.AutoModelForSequenceClassification`, bypassing
  `sentence-transformers` entirely — no `datasets`/`pyarrow` in the import path at all.
- **Neo4j Aura connection fails with `SSLCertVerificationError: self-signed certificate in
  certificate chain`** if the machine has McAfee (or similar) doing HTTPS/TLS inspection —
  it injects its own root CA (look for "Trustwave" in `Cert:\LocalMachine\Root`) that
  Windows trusts but Python's bundled `certifi` store doesn't. Fixed by installing
  `truststore` and calling `truststore.inject_into_ssl()` at the top of `app/main.py`,
  which makes Python's `ssl` module use the OS-native trust store instead. This is not a
  security downgrade (it doesn't disable verification, just changes which CA list is
  consulted) and works identically — with no McAfee involved — on a plain Linux VPS.
- **An Aura Free instance's database is NOT named `neo4j`** — it's named after the
  instance ID (e.g. `878c85b2`, matching the subdomain in the Aura connection URI). Run
  `SHOW DATABASES` against the `system` database to find the real name; set
  `NEO4J_DATABASE` to that, not the literal string `"neo4j"`.
- **NeMo Guardrails' default `self_check_input`/`self_check_output` prompts are too
  aggressive for a document-QA assistant**: a query like "what is the access code in the
  manual?" or an answer that quotes a code/number from the user's own uploaded document
  gets flagged as a jailbreak/unsafe-disclosure attempt and blocked. Fixed by rewriting
  both prompts in `backend/app/guardrails/configs/config.yml` to explicitly say that
  quoting codes/numbers/"sensitive-sounding" terms FROM the user's own uploaded document is
  normal and must not be blocked — only block attempts to manipulate the assistant's own
  instructions. Restart the backend after editing this file (the `LLMRails` config loads
  once at process start).
- **A compound, multi-topic question can trigger the "not relevant to the document"
  fallback even when every sub-fact individually exists in different uploaded documents.**
  The cross-encoder reranker scores each candidate chunk against the *whole* query, so a
  chunk that only answers one part of a 5-part question scores low on the others and can
  fall under `RELEVANCE_THRESHOLD` (`backend/app/core/config.py`). Ask single-topic
  questions, or raise `relevance_threshold` / increase `top_k`, if this matters for your
  use case.
- **A stale `session_token` in the browser's `localStorage` survives a backend restart**
  (the backend's session store is in-memory and resets on restart, but the JWT itself
  looks structurally valid) — this used to fail silently with a generic 404 deep in an API
  call. Fixed with a response interceptor in `frontend/src/api/client.js` that clears
  storage and reloads to the login screen on any 401/404. The driver also explicitly
  clears `localStorage` before each run for the same reason.
- **The frontend originally rendered blank assistant bubbles** — the backend's `/api/chat`
  response field is `answer`, but the chat UI expected `content`. Watch for this class of
  bug if you rename fields on either side; `ChatPage.jsx` maps `response.answer` to
  `content` explicitly when building the assistant turn.

## Troubleshooting

- **`ValueError: Could not connect to Neo4j database`** at backend startup: expected and
  non-fatal if Neo4j isn't reachable — graph search is disabled for that process
  (`graph_search_available: false` in `/api/health`), everything else still works.
- **`OSError: [WinError 4551] An Application Control policy has blocked this file`** on
  `import torch` (or `tiktoken`, `pyarrow`): see the Smart App Control gotcha above — retry
  the same import after a short wait instead of changing any system setting.
- **`curl: (7) Failed to connect`** to `127.0.0.1:8600` or `:5190` right after starting a
  server: the process needs a few seconds to bind — poll (`until curl -sf ...; do sleep 1; done`)
  rather than a single immediate curl.
- **Driver hangs or times out waiting for `.grounded-badge`**: usually means the chat
  request itself errored — check the backend's terminal/log for a traceback (most likely
  cause: `OPENAI_API_KEY` missing/invalid in `backend/.env`).

## VPS deployment note (Hostinger, Linux)

Not yet built/tested — flagged here for when that work starts. On a typical Ubuntu
Hostinger VPS: `sudo apt-get install -y tesseract-ocr` replaces the winget install (no
`TESSERACT_CMD` override needed, it's on `PATH`); the Smart-App-Control and McAfee/Trustwave
gotchas above are Windows-specific and won't apply (though `truststore` is harmless to
leave in — it'll just use Linux's standard CA store); the Vite dual-binding gotcha won't
apply either since you'd build (`npm run build`) and serve static files rather than running
the dev server.
