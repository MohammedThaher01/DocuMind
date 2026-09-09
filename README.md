# DocuMind

**Autonomous Document Generation Agent**

DocuMind bridges the gap between raw LLM text generation and enterprise-grade reliability. It transforms ambiguous, plain-English business requests into formatted `.docx` files through a deterministic, multi-stage ReAct pipeline. Rather than simply completing text, DocuMind prioritizes assumption governance by explicitly identifying missing requirements, resolving commercial conflicts, and auditing its own drafts for mathematical and chronological consistency before delivering a final artifact.

## The Architecture

DocuMind operates on a synchronous REST architecture, decoupling a Vite/React frontend from a Python/FastAPI backend orchestrated by LangGraph.

The agentic pipeline executes in five distinct phases:

* **Classification & Planning:** Parses the user's intent to determine the exact document schema (e.g., Client Proposal, Meeting Minutes, Standard Operating Procedure) and establishes a section-by-section drafting plan.
* **Assumption Extraction:** Explicitly isolates and states any assumptions required to bridge gaps in the original prompt (e.g., assuming a virtual location for a meeting if none was provided).
* **Drafting Execution:** Calls the Groq API to systematically draft each planned section.
* **The Logic Gate (Self-Critique):** A strict validation node intercepts the completed draft. It audits for timeline collisions (e.g., MVP scheduled for both Week 2 and Week 4), mathematical inconsistencies (e.g., workload estimates clashing with team size), and fabricated commercial figures (e.g., unprompted budgets or fixed-price quotes). Unverified specifics are flagged as high-risk assumptions, triggering a revision loop.
* **Document Export:** Compiles the validated draft and operational metadata into a native `.docx` file using `python-docx`, passing a clean download URL back to the client.

## Technical Stack

**Backend System**

* **Python 3.12 / FastAPI:** High-performance, synchronous REST API.
* **LangGraph:** Stateful, graph-based orchestration for the agentic loop.
* **Groq API:** Ultra-low latency LLM inference (optimized for `openai/gpt-oss-20b` or `groq/compound` utilizing JSON mode).
* **python-docx:** Native Word document compilation.

**Frontend Interface**

* **React 18 / Vite:** Lightning-fast component rendering and state management.
* **Tailwind CSS:** Fully responsive, custom dark-mode UI with dynamic SVG status indicators.

## Local Development Setup

**1. Clone the repository**

```bash
git clone https://github.com/MohammedThaher01/DocuMind.git
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
