
# DocuMind

**Autonomous Document Generation Agent**

DocuMind bridges the gap between raw LLM text generation and enterprise-grade reliability. It transforms ambiguous, plain-English business requests into formatted `.docx` files through a deterministic, multi-stage ReAct pipeline. Rather than simply completing text, DocuMind prioritizes assumption governance by explicitly identifying missing requirements, resolving commercial conflicts, and auditing its own drafts for mathematical and chronological consistency before delivering a final artifact.

## System Architecture

DocuMind operates on a synchronous REST architecture, decoupling a Vite/React frontend from a Python/FastAPI backend orchestrated by LangGraph. 

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

## Agentic Execution Pipeline

The LangGraph state machine dictates the flow of data through the following nodes:

* **Classification and Planning:** The agent analyzes the raw user prompt, assigns a strict document schema (e.g., Client Proposal, Meeting Minutes), and generates a section-by-section outline.
* **Assumption Extraction:** The system identifies gaps in the user prompt and explicitly states the business or technical assumptions required to complete the document.
* **Section Drafting:** The orchestration engine iterates through the planned outline, commanding the inference layer to generate targeted content for each section.
* **The Logic Gate (Self-Critique):** A deterministic validation step intercepts the completed draft. It actively audits the text for mathematical inconsistencies, chronological timeline collisions, and unprompted financial figures. If high-risk assumptions or fabrications are detected, the draft is flagged for revision.
* **Revision Loop:** If the Logic Gate flags issues, the agent revises the problematic sections based strictly on the critique feedback.
* **Artifact Export:** The backend compiles the final draft into a `.docx` file, sanitizes the filename to remove hex identifiers, and returns a secure download URL to the client.

## Technical Stack

**Backend System**

* **Python 3.12 / FastAPI:** High-performance, synchronous REST API.
* **LangGraph:** Stateful, graph-based orchestration for the agentic loop.
* **Groq API:** Ultra-low latency LLM inference optimized for `openai/gpt-oss-20b` or `groq/compound` utilizing JSON mode.
* **python-docx:** Native Word document compilation.

**Frontend Interface**

* **React 18 / Vite:** Lightning-fast component rendering and state management.
* **Tailwind CSS:** Fully responsive, custom dark-mode UI with dynamic SVG status indicators.

## Local Development Setup

**1. Clone the repository**

```bash
git clone [https://github.com/MohammedThaher01/DocuMind.git](https://github.com/MohammedThaher01/DocuMind.git)
cd DocuMind

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

# Point Vite to the local API
echo "VITE_API_URL=http://localhost:8000" > .env

# Start the development server
npm run dev

```

## Core API Surface

The backend exposes a minimal, highly deliberate API surface designed to prevent asynchronous state leakage:

* `POST /agent`
Accepts a JSON payload containing the user's raw prompt. Executes the complete LangGraph orchestration loop and returns the execution status, stated assumptions, task list, and the final artifact locator.
* `GET /download/{filename}`
Serves the generated `.docx` file using FastAPI's `FileResponse`. Implements regex sanitization to strip backend hex identifiers and format the file with clean Title Casing before forcing a native browser download.

## Deployment

DocuMind is configured for immediate deployment on platforms like Railway or Render. The application executes as a unified full-stack service. The React application is built statically into the `dist/` directory, and the FastAPI application mounts and serves these static assets alongside the API endpoints from a single container instance.

*Developed by Mohammed Thaher S*

```

```
