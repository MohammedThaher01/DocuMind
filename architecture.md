# DocuMind — System Architecture

## Overview

DocuMind is an AI-assisted document-generation agent built with FastAPI, LangGraph, Groq, React, Vite, and `python-docx`. It accepts a natural-language business request, plans a document, drafts its sections, checks the assembled draft, performs at most one revision pass when material problems are found, and exports a Word document.

The current API is synchronous. The browser waits for `POST /agent` to return. The current implementation does not use server-sent events (SSE), background job IDs, or job polling.

## Components

### React frontend

- Collects the user's document request.
- Sends a JSON request to `POST /agent`.
- Displays the document type, planned task list, assumptions, validation critique, final status, and unresolved issues.
- Links to the generated `.docx` download.

### FastAPI backend

- Validates the request body with Pydantic.
- Invokes the compiled LangGraph workflow synchronously.
- Returns the generation result and validation metadata.
- Serves generated files through `GET /download/{filename}`.
- Serves the production SPA from `frontend/dist` when the frontend build is present.
- Exposes `GET /health` and FastAPI's interactive `GET /docs` page.

### LangGraph workflow

The graph manages the planning, drafting, validation, bounded revision, revalidation, and export stages. State includes the original request, planned sections, assumptions, draft sections, critique results, revision count, final status, and generated file path.

### Groq language model

The LLM helps classify and plan the document, draft sections, critique the draft, and revise it. LLM output is treated as generated content rather than proof of factual accuracy.

### Deterministic validation helpers

Deterministic checks inspect selected source constraints, including supported figure and unit patterns. They complement the LLM critic; they are not a complete semantic or factual verification system.

### `python-docx`

Creates the downloadable Word file with the title, document type, assumptions, sections, execution log, and a human-review warning when material issues remain after the allowed revision pass.

## Workflow

1. **Plan:** Classify the request, choose document sections, and record assumptions for ambiguity or missing details.
2. **Draft:** Generate the planned sections using the original request and stated assumptions. Do not present invented names, figures, dates, policies, or commitments as facts.
3. **Reflect:** Compare the assembled draft with the original request. Run supported deterministic checks and an LLM critique.
4. **Route:** If material issues are found, or if the critique cannot be parsed, spend the single allowed revision pass. Otherwise, proceed to export.
5. **Revise:** Ask the model to address the issues while preserving the number and headings of the planned sections. Reject a malformed or structurally incomplete revision.
6. **Revalidate:** Run validation again after the revision. If material issues remain, set `review_required` and surface the unresolved issues.
7. **Export:** Create the DOCX and return the response, latest critique, assumptions, task list, revision metadata, final status, and download URL.

```text
User
  |
  v
React frontend
  |
  | POST /agent
  v
FastAPI
  |
  v
Plan --> Draft sections --> Initial reflection
                             |
                      +------+------+
                      |             |
                   No issues     Issues / invalid critique
                      |             |
                      |          Revise once
                      |             |
                      |          Revalidate
                      |             |
                      +------+------+
                             |
                             v
                         Export DOCX
                             |
                             v
                      Return API result
```

## Assumption and Validation Policy

- Preserve facts, figures, dates, units, and constraints explicitly supplied by the user.
- Make planning assumptions visible in the response and generated document.
- Do not silently turn a missing value into a claimed fact or a verified business result.
- Treat a malformed critique as a validation failure, not as a clean pass.
- Attempt no more than one automatic revision pass.
- If material findings remain after revalidation, mark the result `review_required` and include the unresolved issues in the response and document.
- Report validation as a quality gate, not as a guarantee that all content is true.

The deterministic checks cover only patterns implemented in code. The LLM critic can miss issues or produce incorrect findings. Consequential documents should be reviewed by an appropriate person before use.

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /agent` | Run the document-generation workflow synchronously |
| `GET /download/{filename}` | Download a generated DOCX file |
| `GET /health` | Return health status and configured model identifier |
| `GET /docs` | Open the interactive API documentation |

The `POST /agent` response includes `message`, `doc_type`, `assumptions`, `task_list`, `revised`, `download_url`, `status`, `review_required`, `revision_count`, `unresolved_issues`, and `critique`.

## Deployment

The repository is configured for a single-service deployment when the frontend is built into `frontend/dist` and served by FastAPI. Build the frontend before starting the backend.

Required environment variable:

- `GROQ_API_KEY` — API key for Groq.

Optional environment variables:

- `GROQ_MODEL` — model identifier supported by the Groq account.
- `ALLOWED_ORIGINS` — comma-separated browser origins permitted for cross-origin development or split deployment.

Never commit API keys or secrets to source control.
