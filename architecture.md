I double-wrapped the Markdown block in my previous response, which breaks the formatting and exposes the raw backticks instead of rendering cleanly.

Here is a visual text-based flowchart you can view directly, followed by the clean Markdown text for your repository.

**Architecture Flowchart**

```text
[ User ]
   |
   | (Plain English Prompt)
   v
[ React Frontend ]
   |
   | (POST /agent)
   v
[ FastAPI Backend ]
   |
   +---> [ Classification & Planning ]
                 |
                 v
         [ Assumption Extraction ]
                 |
                 v
         [ Section Drafting ]
                 |
                 v
         { Logic Gate: Self-Critique } <---+
                 |                         |
          (Issues Detected)                |
                 v                         |
         [ Revision Loop ] ----------------+
                 |
            (Validated)
                 v
   +---> [ Artifact Export .docx ]
   |
   | (Returns download_url)
   v
[ React Frontend ]
   |
   | (GET /download/[filename])
   v
[ FastAPI Backend ]
   |
   | (Native File Download)
   v
[ User ]

```

---

# DocuMind System Architecture

## System Overview

DocuMind is a unified full-stack application leveraging a synchronous REST architecture. The system integrates a client-side React frontend with a Python-based FastAPI backend, utilizing LangGraph as the stateful orchestration engine for the autonomous agent.

## Architecture Flowchart

```mermaid
graph TD
    User([User]) -->|Plain English Prompt| UI[React Frontend]
    
    UI -->|POST /agent| API[FastAPI Backend]
    
    subgraph LangGraph Execution Pipeline
        API --> Plan[Classification & Planning]
        Plan --> Assume[Assumption Extraction]
        Assume --> Draft[Section Drafting]
        Draft --> Critique{Logic Gate: Self-Critique}
        
        Critique -->|Issues Detected| Revise[Revision Loop]
        Revise --> Critique
        
        Critique -->|Validated| Export[Artifact Export .docx]
    end
    
    Export -->|Returns download_url| UI
    UI -->|GET /download/[filename]| API
    API -->|Native File Download| User

```

## Core Components

* **Frontend (React 18, Vite, Tailwind CSS):** A single-page application that captures user intent and displays execution status. It communicates with the backend via a single synchronous POST request and handles native browser file downloads dynamically.
* **Backend (FastAPI, Python 3.12):** A high-performance web framework responsible for executing the API endpoints, managing file streams, and serving the compiled static frontend assets.
* **Orchestration Engine (LangGraph):** Manages the deterministic execution loop of the AI agent, ensuring tasks flow sequentially through planning, drafting, validation, and export phases.
* **Inference Layer (Groq API):** Provides ultra-low latency LLM text generation, relying on structured JSON mode for reliable data parsing.
* **Document Generation (python-docx):** Compiles the validated text structures into native Word documents.

## Agentic Execution Pipeline

The LangGraph state machine dictates the flow of data through the following nodes:

1. **Classification and Planning:** The agent analyzes the raw user prompt, assigns a strict document schema (e.g., Client Proposal, Meeting Minutes), and generates a section-by-section outline.
2. **Assumption Extraction:** The system identifies gaps in the user prompt and explicitly states the business or technical assumptions required to complete the document.
3. **Section Drafting:** The orchestration engine iterates through the planned outline, commanding the inference layer to generate targeted content for each section.
4. **The Logic Gate (Self-Critique):** A deterministic validation step intercepts the completed draft. It actively audits the text for mathematical inconsistencies, chronological timeline collisions, and unprompted financial figures. If high-risk assumptions or fabrications are detected, the draft is flagged for revision.
5. **Revision Loop:** If the Logic Gate flags issues, the agent revises the problematic sections based strictly on the critique feedback.
6. **Artifact Export:** The backend compiles the final draft into a `.docx` file, sanitizes the filename to remove hex identifiers, and returns a secure download URL to the client.

## Data Flow

* The user submits a plain English prompt via the React UI.
* The frontend initiates a `POST /agent` request containing the JSON payload.
* FastAPI routes the payload to the LangGraph execution environment.
* LangGraph manages the conversational state and calls the Groq API multiple times for planning, drafting, and reflection.
* Upon successful validation, the backend saves the `.docx` file to a local output directory.
* The backend responds to the frontend with execution metadata and a structured `download_url`.
* The frontend bypasses popup blockers by assigning the window location to `GET /download/[filename]`, triggering the browser's native file download process.

## Deployment Model

The application uses a monolithic deployment strategy to maximize operational simplicity and stability. The React frontend is compiled into static assets within a `dist/` directory. The FastAPI server is configured to mount this directory and serve the UI alongside the API endpoints from a single unified container on platforms like Railway or Render. This eliminates Cross-Origin Resource Sharing (CORS) complexity and guarantees resilient routing between the frontend and the agent backend.
