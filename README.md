# Unofficial UE Chatbot

An unofficial RAG-based assistant that helps Uber Eats riders in the Netherlands quickly consult work regulations, contracts, and internal documentation — without waiting for unresponsive offices.

> **Disclaimer:** This is a personal, unofficial project with no affiliation with Uber or Adecco. It is provided as-is, for informational purposes only. Always verify critical information with official sources.

**Live:** [unofficial-ue-chatbot.fly.dev](https://unofficial-ue-chatbot.fly.dev)

---

## What it does

Riders can ask questions in any language — English, Arabic, Dutch, Italian, or others — and receive answers grounded in real documentation: employment contracts, the CAO (Collective Labour Agreement), payslip guides, platform regulations, and internal operational updates.

Example queries:
- *"What do I do if I'm sick and can't work?"*
- *"How is my holiday pay calculated?"*
- *"Who do I contact for payslip issues?"*
- *"ماذا أفعل إذا كنت مريضاً؟"* (Arabic)
- *"Hoeveel vakantiedagen heb ik?"* (Dutch)

---

## Architecture

```
User query (any language)
    ↓
Language detection (langdetect, local ~1ms)
    ↓
Query translation to English (if needed) — via LLM
    ↓
Query rewriting for context (conversational memory)
    ↓
Hybrid Search: pgvector (semantic) + Postgres FTS (lexical)
Reciprocal Rank Fusion (RRF)
    ↓
Cohere Rerank 3.5 — cross-encoder reranking
    ↓
Top-5 chunks → LLM context assembly
    ↓
Gemini 2.5 Flash Lite — answer generation (streaming)
    ↓
Response in user's language + cited sources
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI + uvicorn |
| LLM | Gemini 2.5 Flash Lite via OpenRouter |
| Embeddings | text-embedding-3-small (OpenAI) |
| Vector DB | Supabase (pgvector) |
| Hybrid Search | pgvector + Postgres FTS + RRF |
| Reranker | Cohere Rerank 3.5 API |
| Frontend | Vanilla HTML/CSS/JS (mobile-first) |
| Hosting | Fly.io (Amsterdam region) |
| PDF Parsing | pymupdf4llm |

---

## Knowledge Base

46 documents, ~887 chunks covering:

- **Contracts:** Arbeidsovereenkomst, CAO voor Uitzendkrachten 2026-2028, Uitzendbevestiging
- **Regulations:** Wegenverkeerswet 1994 (Dutch Road Traffic Act)
- **Platform policies:** Uber Community Guidelines, Platform Terms, Privacy Notice, UberPro Terms
- **Operational:** Payslip guide, payroll tax overview, performance metrics, shift rules
- **Support FAQs:** 26 Uber Eats support articles (account setup, documents, payments, troubleshooting)
- **Internal:** Discord updates, contact routing, sick leave protocol

Languages: English (primary), Dutch, Italian (partial)

---

## Project Structure

```
src/
├── api/
│   ├── app.py          ← FastAPI + SSE streaming endpoint
│   ├── llm.py          ← LLM calls + query translation + rewriting
│   ├── pipeline.py     ← orchestration: retrieval → context → answer
│   └── prompt.py       ← system prompt (11 rules)
├── retrieval/
│   ├── retriever.py    ← vector_search, fts_search, hybrid_search, search()
│   └── reranker.py     ← Cohere Rerank 3.5 integration
├── ingestion/
│   ├── pipeline.py     ← ingest_all() with file_filter support
│   ├── parser.py       ← PDF parsing (pymupdf4llm)
│   ├── parser_text.py  ← TXT/MD parsing
│   ├── chunker.py      ← semantic chunking on Markdown headers
│   └── embedder.py     ← OpenAI batch embeddings
└── diagnostics/
    └── timing.py       ← TTFT benchmarking
frontend/
└── index.html          ← mobile-first chat UI with streaming
```

---

## Key Design Decisions

**Hybrid search over pure vector search** — lexical search catches exact terms (contract names, article numbers) that semantic search misses. RRF fusion requires no weight calibration.

**Cohere Rerank over local reranker** — pyarrow crashes on Python 3.13 + Windows, making local cross-encoders (bge-reranker-v2-m3) uninstallable without downgrading. Cohere API solves this at ~$0.002/query. Migration path documented: rewrite only `reranker.py` when volume exceeds 12,500 queries/month.

**Gemini 2.5 Flash Lite over Qwen3-8B** — migrated post-testing when Qwen showed unacceptable latency on Arabic queries with long CAO chunks. Gemini is more robust on multilingual instruction-following at small model sizes.

**langdetect for language detection** — local library (~1ms) replacing a second LLM call, saving ~3s per non-English query.

**Conversational memory in browser only** — 4-turn window stored in session, no DB persistence. Zero privacy risk, zero schema changes.

**SSE streaming** — first tokens visible in ~1-2 seconds despite 10-15s total generation time. Critical for perceived responsiveness on mobile.

---

## Multilingual Support

- **Detection:** langdetect (local)
- **Translation:** query translated to English before retrieval, answer generated in original language
- **Arabic:** MSA (Modern Standard Arabic) output. Dialects (Egyptian, Moroccan Darija, Levantine) understood in input, answered in MSA — structural model limitation, not architectural
- **Dutch:** full support, FTS configured with Dutch stemming

---

## Running Locally

```bash
# Clone and install
git clone https://github.com/Kawchee/unofficial_ue_chatbot.git
cd unofficial_ue_chatbot
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # add your API keys

# Start server
uvicorn src.api.app:app --reload --port 8000 --host 0.0.0.0
```

Open `http://localhost:8000` in your browser.

**Required API keys:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `COHERE_API_KEY`

---

## Deployment

Hosted on Fly.io (Amsterdam). To deploy updates:

```bash
git add .
git commit -m "description"
git push
flyctl deploy
```

---

## Limitations

- **Math calculations:** the LLM is unreliable on complex arithmetic. Workaround: pre-calculated examples in source documents for common cases (net salary from gross, holiday pay).
- **Missing information:** if a document hasn't been ingested, the system correctly says "I don't have this information" rather than hallucinating.
- **Legal disclaimer:** the CAO is binding in its Dutch text. English version is a translation for convenience.

---

## Cost Estimate (at full scale — 110k queries/month)

| Component | Cost/month |
|---|---|
| Gemini 2.5 Flash Lite (LLM) | ~$5-15 |
| OpenAI embeddings | ~$3 |
| Cohere Rerank 3.5 | ~$220 |
| Fly.io hosting | ~$0.50-2 |
| **Total** | **~$230-240** |

At current low volume: <$5/month total.

Reranker migration to local bge-reranker-v2-m3 recommended when volume exceeds 12,500 queries/month (break-even point).

---

*Built as a learning project exploring production RAG architecture. Contact: unofficial.uechatbot.assistanc@gmail.com*
