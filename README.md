# DocuMind — Autonomous Document-Generation Agent

A FastAPI + LangGraph agent that takes a natural-language business request, autonomously plans the tasks needed, executes each step using Groq LLM, performs a self-reflection/critique pass, revises the content, and generates a polished .docx document. Ships with a Vite + React + Tailwind frontend and a single-service Railway (Nixpacks) deploy config.

**Live demo:** https://docu-mind.up.railway.app

## Features

- **Multi-Step Planning**: Classifies document type, decides sections, and states assumptions for ambiguous requirements
- **Section-by-Section Execution**: Generates content with focused LLM calls
- **Self-Reflection & Revision**: Quality gate with critique and revision
- **Polished DOCX Output**: Professional document with assumptions and execution log
- **Live Progress UI**: React frontend showing the task checklist, assumptions panel, self-critique panel, and one-click .docx download

## Tech Stack

- **FastAPI**: Web framework for the API
- **LangGraph**: Orchestrates the agent's state and workflow (plan → execute → reflect → revise → revalidate → export)
- **Groq**: LLM provider for fast inference
- **python-docx**: Generates the final .docx documents
- **Vite + React**: JavaScript frontend
- **Tailwind CSS v3**: Styling (Inter font, SaaS-grade gradients)
- **Railway (Nixpacks)**: Single-service deploy configured via `nixpacks.toml`

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

**2. Configure the Backend**

```bash
# Initialize a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
echo "GROQ_API_KEY=your_groq_api_key_here" > .env

```

**3. Boot the FastAPI Server**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

```

**4. Configure the Frontend**

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server
npm run dev

```

## Usage

### Endpoint: `POST /agent`

Runs the document-generation workflow synchronously — the request blocks until the graph finishes and returns the final document object. The frontend renders the task checklist, assumptions, and critique once the call returns.

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"request": "Create meeting minutes for our weekly engineering standup. Attendees were Priya, Arjun and Neha. We discussed sprint progress, a bug in the payment module, and next sprint planning."}'
```

The response is the final document object described below. Two canonical test cases (simple + ambiguous) live in the test suite.

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

The agent is a LangGraph state graph: `plan → execute → reflect —(if material issues)→ revise → revalidate → export → END`. The `revalidate` node always leads to export, and a document with unresolved material issues is exported as `review_required`. See [architecture.md](architecture.md) and [main.py](main.py).

---

## Deployment

DocuMind deploys as a **single service on Railway** using [nixpacks.toml](nixpacks.toml). Nixpacks installs the Python and Node dependencies, builds the Vite frontend into `frontend/dist`, and starts uvicorn; FastAPI then serves both the API and the built SPA from one origin.

1. Push the project to GitHub.
2. On Railway → **New Project** → **Deploy from GitHub repo** → pick this repo. Railway auto-detects `nixpacks.toml`.
3. Under the service's **Variables** tab, add `GROQ_API_KEY` (and optionally `GROQ_MODEL` / `ALLOWED_ORIGINS`).
4. Railway builds and serves the app on the generated public domain. Visit `/` for the UI or `/docs` for the API.

> The generated `.docx` files are written to `generated_docs/`. Mount a Railway **Volume** at that path so downloads survive redeploys and restarts.

> The frontend calls the API at the relative path `/agent`, so the single-service setup needs no CORS configuration. If you split the frontend onto a separate host (e.g. Vercel via the bundled `frontend/vercel.json`), set `ALLOWED_ORIGINS` on the backend to include the frontend's origin.

## Environment Variables

| Variable | Where | Required | Default |
|---|---|---|---|
| `GROQ_API_KEY` | Backend | ✅ | — |
| `GROQ_MODEL` | Backend | ❌ | `llama3-70b-8192` |
| `ALLOWED_ORIGINS` | Backend | ❌ (localhost friendly) | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000` |

## License

MIT

