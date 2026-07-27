# DocuMind 📄 — Autonomous Document-Generation Agent

A FastAPI + LangGraph agent that takes a natural-language business request, autonomously plans the tasks needed, executes each step using Groq LLM, performs a self-reflection/critique pass, revises the content, and generates a polished .docx document. Ships with a Vite + React + Tailwind frontend and production deploy configs for Render + Vercel.

## Features

- **Multi-Step Planning**: Classifies document type, decides sections, and states assumptions for ambiguous requirements
- **Section-by-Section Execution**: Generates content with focused LLM calls
- **Self-Reflection & Revision**: Quality gate with critique and revision
- **Polished DOCX Output**: Professional document with assumptions and execution log
- **Live Progress UI**: React frontend with SSE-streamed task checklist, assumptions panel, self-critique panel, and one-click .docx download

## Tech Stack

- **FastAPI**: Web framework for the API
- **LangGraph**: Orchestrates the agent's state and workflow (plan → execute → reflect → revise → export)
- **Groq**: LLM provider for fast inference
- **python-docx**: Generates the final .docx documents
- **Vite + React**: JavaScript frontend
- **Tailwind CSS v3**: Styling (Inter font, SaaS-grade gradients)
- **Docker + render.yaml**: One-click deploy to Render

## Getting Started

### Prerequisites

1. Python 3.10+
2. Node.js 18+ (for the frontend)
3. Groq API key (get one free at [console.groq.com](https://console.groq.com))

### Installation — Backend

1. Clone the repository:
   ```bash
   git clone <your-repo-url> documind
   cd documind
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file:
     ```env
     GROQ_API_KEY=your_groq_api_key_here
     # Optional:
     # GROQ_MODEL=llama-3.3-70b-versatile
     # ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend.example.com
     ```

4. Run the backend:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   API docs: `http://127.0.0.1:8000/docs`

### Installation — Frontend

```bash
cd frontend
npm install
# Optional: create frontend/.env and point to a remote backend
# VITE_API_URL=https://your-backend.onrender.com
npm run dev
# -> http://localhost:5173
```

## Usage

### Async API Endpoint: `POST /agent`

Kicks off document generation asynchronously. Returns a `job_id` you can stream via SSE or poll.

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Create meeting minutes for our weekly engineering standup. Attendees were Priya, Arjun and Neha. We discussed sprint progress, a bug in the payment module, and next sprint planning."}'
```

Response:
```json
{
  "job_id": "abc123def456",
  "status_endpoint": "/agent/abc123def456",
  "stream_endpoint": "/agent/abc123def456/stream"
}
```

Then stream progress with EventSource on `/agent/{job_id}/stream` (emits typed events: `queued`, `start`, `node`, `task_list`, `plan`, `critique`, `export`, `done`, `error`) or poll `/agent/{job_id}`.

### Legacy sync endpoint (backward compat): `POST /agent/sync`

Blocks until the graph finishes and returns the final document object — useful for curl / quick testing. See [TEST REQUESTS.md](TEST%20REQUESTS.md) for two canonical test cases (simple + ambiguous).

### Response shape (final result)

```json
{
  "message": "Successfully generated a meeting minutes document.",
  "doc_type": "meeting_minutes",
  "assumptions": [
    "The meeting was held remotely",
    "The sprint is currently in the middle of its cycle"
  ],
  "task_list": [
    {"step": 0, "title": "Classify request -> meeting_minutes", "status": "done"},
    {"step": 1, "title": "Draft section: Attendees", "status": "done"},
    {"step": 2, "title": "Draft section: Sprint Progress", "status": "done"},
    {"step": 3, "title": "Draft section: Bug Discussion", "status": "done"},
    {"step": 4, "title": "Draft section: Next Sprint Planning", "status": "done"},
    {"step": 5, "title": "Self-critique draft", "status": "done"},
    {"step": 6, "title": "Export to DOCX", "status": "done"}
  ],
  "revised": false,
  "download_url": "/download/meeting_minutes_12816346.docx"
}
```

## Architecture

The agent is a LangGraph state graph: `plan → execute → reflect —(if needs_revision)→ revise → export → END`. See [architecture.md](architecture.md) and [main.py](main.py).

---

## Deployment

### Option A — One-click on Render (recommended: both services together)

1. Push the project to GitHub.
2. In `render.yaml`, update the two `repo:` URLs and `VITE_API_URL` / `ALLOWED_ORIGINS` placeholders to match your actual backend URL after first deploy.
3. On Render → **Blueprints** → **New Blueprint Instance** → pick your repo.
4. When prompted, paste your `GROQ_API_KEY` as the value for the `documind-backend → GROQ_API_KEY` env var (sync: false, enter manually).
5. After both services deploy:
   - Copy the frontend's `.onrender.com` URL → paste it into backend's `ALLOWED_ORIGINS` env var → redeploy backend.
   - Copy the backend's `.onrender.com` URL → paste into frontend's `VITE_API_URL` env var → redeploy frontend.
6. (Optional) Mount a Render persistent disk at `/app/generated_docs` in the backend service so `.docx` files survive deploys and restarts.

### Option B — Backend on Render, Frontend on Vercel

**Backend (Render Docker deploy)**
- New → Web Service → pick repo → Runtime = **Docker** → root dir = repo root.
- Add env var `GROQ_API_KEY` = your key.
- Add env var `ALLOWED_ORIGINS` = `https://<your-vercel-domain>.vercel.app`.
- Build completes; service is live at `https://<name>.onrender.com`.

**Frontend (Vercel)**
- Import the repo → set **Root Directory = `frontend`** → Framework = **Vite** (auto-detected).
- Add env var `VITE_API_URL` = `https://<your-backend>.onrender.com` (no trailing slash).
- Deploy. `frontend/vercel.json` already contains the SPA rewrite rules.

## Environment Variables

| Variable | Where | Required | Default |
|---|---|---|---|
| `GROQ_API_KEY` | Backend | ✅ | — |
| `GROQ_MODEL` | Backend | ❌ | `llama-3.3-70b-versatile` |
| `ALLOWED_ORIGINS` | Backend | ❌ (localhost friendly) | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,*` |
| `VITE_API_URL` | Frontend (build-time) | ❌ for local, ✅ for deploy | `http://localhost:8000` |

## License

MIT

