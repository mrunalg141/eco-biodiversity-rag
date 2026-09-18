# ECO: AI Biodiversity Intelligence

An evidence-grounded conversational system for environmental/agricultural
advisory, built for Darukaa.Earth's *AI Biodiversity Intelligence Chatbot
Challenge*. The app also supports general document Q&A over uploaded PDFs.

## Features

**Environmental advisory (new)**
- Categorized knowledge base (soil, climate, biodiversity, land_use, human_impact)
  indexed from real FAO / IPCC / IPBES / UNCCD reports — not generic LLM knowledge
- Multi-category retrieval: every query pulls matches from each of the 5
  categories separately, so recommendations connect ≥3 real variables instead
  of answering off one
- If fewer than 3 categories return a relevant match, the system says so
  honestly instead of fabricating cross-category depth
- Structured, source-cited output (recommendation, reasoning, impacted
  metrics, time horizon, confidence, sources) via a Pydantic schema
- Clarifying-question flow: mentioning "biodiversity" in `/chat` prompts the
  system to ask for soil organic carbon %, rainfall, and land use before
  answering, rather than guessing
- A dedicated structured-input endpoint (`/environment/recommend`) for
  JSON input alongside the conversational path

**Document Q&A**
- Upload a PDF and ask questions about its content
- Answers grounded only in the document — no hallucinated info outside its context
- Fast inference via the Groq API (OpenAI-compatible)
- Semantic search over document chunks using vector embeddings
- Persistent chat history (SQLite)

## Tech Stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript (vanilla), Jinja2 templates |
| LLM | Groq API (OpenAI-compatible), `openai/gpt-oss-20b` |
| Embeddings | fastembed (`BAAI/bge-small-en-v1.5`) |
| Vector store | ChromaDB — two collections: `studymate_docs` (user uploads) and `env_knowledge_base` (fixed, categorized) |
| Structured output | Pydantic |
| Chat history | SQLite |

## How It Works

**Document Q&A path:** upload → extract (`pypdf`) → chunk (~250-word,
overlapping) → embed (`fastembed`) → store in `studymate_docs` → on question,
embed + retrieve top matches → reject weak matches by distance threshold →
answer grounded in retrieved chunks only.

**Environmental advisory path:** input (via `/chat` after the clarifying
question, or directly via `/environment/recommend`) → query embedded and
retrieved separately against each of the 5 categories in `env_knowledge_base`
→ if ≥3 categories return a match, retrieved chunks (with source + category
tags) are passed to the LLM under a system prompt that forbids fabricated
citations and requires connecting ≥3 variables → response parsed into the
structured `Recommendation` schema.

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Renders the chat UI |
| `/upload` | POST | Upload a PDF into `studymate_docs` |
| `/chat` | POST | Conversational endpoint — handles both PDF Q&A and the biodiversity clarifying-question flow |
| `/environment/recommend` | POST | Structured JSON input → direct environmental recommendation |
| `/clear` | POST | Clears chat history, uploaded documents, and in-memory environmental state |
| `/test-embed` | GET | Embedder warmup/benchmark check |

## Recommendation output schema

```python
class Recommendation(BaseModel):
    recommendation: str
    reasoning: str
    metrics_impacted: list[str]
    time_horizon: str
    confidence: str          # "low" | "medium" | "high"
    sources: list[str]       # real source_ids from retrieved chunks
```

## Project Structure

```
ECO/
├── app/
│   ├── main.py
│   ├── llm.py              # get_ai_reply, get_environmental_recommendation, get_environmental_followup
│   ├── rag.py               # embedder, index_pdf, retrieve_context, retrieve_context_by_category, build_env_knowledge_base
│   └── database.py
├── chroma_db/                # persistent vector store (both collections)
├── knowledge_base/
│   ├── soil/
│   ├── climate/
│   ├── biodiversity/
│   ├── land_use/
│   └── human_impact/
├── script/                   # build_knowledge_base.py
├── static/
│   ├── style.css
│   └── script.js
├── templates/
│   └── index.html
├── uploads/                  # user-uploaded PDFs for the document Q&A path
├── chat_history.db           # SQLite chat history
├── requirements.txt
├── .env
└── .gitignore
```

## Prerequisites

- Python 3.9+
- A [Groq API key](https://console.groq.com)

## Setup

1. Clone the repo
   ```bash
   git clone <your-repo-url>
   cd ECO
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Mac/Linux
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Add your Groq API key — create a `.env` file in the project root:
   ```
   GROQ_API_KEY=your_api_key_here
   ```

5. Build the environmental knowledge base (one-time, or whenever you add
   PDFs to `knowledge_base/<category>/`):
   ```bash
   python script/build_knowledge_base.py
   ```

6. Run the app:
   ```bash
   uvicorn app.main:app --reload
   ```

7. Open `http://127.0.0.1:8000`

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | API key used to authenticate requests to the Groq LLM |

## Usage

**PDF Q&A:** upload a PDF, wait for processing, then ask questions about it.

**Environmental advisory:** type a message mentioning "biodiversity" in the
chat, then reply with `soil_organic_carbon, rainfall, land_use` (e.g.
`0.3%, low, monoculture wheat`) when prompted — or POST directly to
`/environment/recommend` with structured JSON.

## Known limitations / next steps

- `environmental_state` is a single in-memory dict keyed by a hardcoded
  `"default"` user — it does not yet support multiple concurrent users/sessions.
- `get_environmental_followup()` exists in `app/llm.py` but isn't currently
  called from any route — either wire it in or remove the unused import.
- Conversational memory beyond the single clarifying-question exchange (e.g.
  pulling prior SQLite chat history into the LLM prompt) is not yet implemented.
- `land_use` and `human_impact` categories each currently rely on a single
  source document.
