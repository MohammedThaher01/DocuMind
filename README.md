# Autonomous Document-Generation Agent

A FastAPI + LangGraph agent that takes a natural-language business request, autonomously plans the tasks needed, executes each step using Groq LLM, performs a self-reflection/critique pass, revises the content, and generates a polished .docx document.

## Features

- **Multi-Step Planning**: Classifies document type, decides sections, and states assumptions for ambiguous requirements
- **Section-by-Section Execution**: Generates content with focused LLM calls
- **Self-Reflection & Revision**: Quality gate with critique and revision
- **Polished DOCX Output**: Professional document with assumptions and execution log

## Tech Stack

- **FastAPI**: Web framework for the API
- **LangGraph**: Orchestrates the agent's state and workflow
- **Groq**: LLM provider for fast inference
- **python-docx**: Generates the final .docx documents

## Getting Started

### Prerequisites

1. Python 3.10+
2. Groq API key (get one free at [console.groq.com](https://console.groq.com))

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/MohammedThaher01/fluid-ai-
   cd fluid-ai-
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Copy `.env.example` (if exists) or create a `.env` file:
     ```env
     GROQ_API_KEY=your_groq_api_key_here
     ```

### Running the Server

```bash
uvicorn main:app --reload --port 8000
```

The API docs will be available at `http://127.0.0.1:8000/docs`

## Usage

### API Endpoint: POST /agent

Send a natural language request to generate a document:

```json
{
  "request": "Create meeting minutes for our weekly engineering standup. Attendees were Priya, Arjun and Neha. We discussed sprint progress, a bug in the payment module, and next sprint planning."
}
```

### Response Example

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

For a detailed system architecture diagram, see [architecture.md](architecture.md).

## License

MIT
