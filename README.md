# Unofficial UE Chatbot

An unofficial RAG-based chatbot assistant that helps Uber Eats riders in the Netherlands quickly consult work regulations, contracts, and internal documentation. Built as a personal learning project exploring production RAG architecture: semantic chunking, hybrid search, Cohere reranking, streaming responses, and multilingual query translation.

> \\\\\\\*\\\\\\\*Disclaimer:\\\\\\\*\\\\\\\* This project has no affiliation with Uber or Adecco. It is provided as-is, for informational purposes only. The information provided may be wrong, incomplete, or outdated. Always double-check with official sources.

**Live:** [unofficial-ue-chatbot.fly.dev](https://unofficial-ue-chatbot.fly.dev)

\---

## What it does

Riders can ask questions in any language and receive answers grounded in real documentation: employment contracts, the CAO (Collective Labour Agreement), payslip guides, platform regulations, and internal operational updates.

\---

## Architecture

```
User query (any language)

\\\&#x20;   ↓

Language detection + translation to English — single LLM call

(no-op cost if already English: \\\\\\\~50 input / \\\\\\\~20 output tokens)

\\\&#x20;   ↓

Query rewriting for conversational context — LLM call

(skipped if no conversation history)

\\\&#x20;   ↓

Hybrid Search: pgvector (semantic) + Postgres FTS (lexical)

Reciprocal Rank Fusion (RRF)

\\\&#x20;   ↓

Cohere Rerank 3.5 — cross-encoder reranking

\\\&#x20;   ↓

Top-5 chunks → LLM context assembly

\\\&#x20;   ↓

Gemini 2.5 Flash Lite — answer generation (streaming)

\\\&#x20;   ↓

Response in user's language (sources retrieved but not shown — see frontend/index.sources.html for technical use cases)
```

\---

## Tech Stack

|Component|Technology|
|-|-|
|Backend|FastAPI + uvicorn|
|LLM|Gemini 2.5 Flash Lite via OpenRouter|
|Embeddings|text-embedding-3-small (OpenAI)|
|Vector DB|Supabase (pgvector)|
|Hybrid Search|pgvector + Postgres FTS + RRF|
|Reranker|Cohere Rerank 3.5 API|
|Frontend|Vanilla HTML/CSS/JS (mobile-first)|
|Hosting|Fly.io (Amsterdam region)|
|PDF Parsing|pymupdf4llm|

\---

## Knowledge Base

46 documents, \~887 chunks covering:

* **Contracts**
* **Regulations**
* **Platform policies**
* **Operational**
* **Support FAQs**
* **Personal notes**

Languages: English (primary), Dutch

\---

## Project Structure

```
ChatbotRAG\\\\\\\_UberEats/

├── run\\\\\\\_ingestion.py         	← entry point: ingests all documents into Supabase

│

├── frontend/

│   ├── index.html             		← mobile-first chat UI with SSE streaming (active)

│   └── index.sources.html     		← alternative UI with visible sources panel (technical users)

│

├── src/

│   ├── api/

│   │   ├── app.py             		← FastAPI app + /chat streaming endpoint (SSE)

│   │   ├── llm.py             		← LLM client, query translation, query rewriting, MODEL

│   │   ├── pipeline.py        		← RAG orchestration pipeline (used by benchmark)

│   │   └── prompt.py          		← system prompt + rewrite prompt

│   ├── retrieval/

│   │   ├── retriever.py       		← vector search, FTS, hybrid search (RRF), search()

│   │   └── reranker.py        		← Cohere Rerank 3.5

│   ├── ingestion/

│   │   ├── pipeline.py        		← ingest\\\\\\\_all() with cleanup + file\\\\\\\_filter support

│   │   ├── parser.py			← PDF parsing via pymupdf4llm

│   │   ├── parser\\\\\\\_text.py   	← TXT/MD parsing

│   │   ├── chunker.py         		← semantic chunking on Markdown headers

│   │   └── embedder.py   		← OpenAI batch embeddings (text-embedding-3-small)

│   └── diagnostics/

│       └── timing.py      		← timed() context manager for latency measurement

│

├── scripts/

│   ├── benchmark\\\\\\\_ttft.py    	← per-step latency benchmark (runs full pipeline)

│   └── check\\\\\\\_db.py          	← diagnostic: compares data/raw with Supabase

│

├── smoke\\\\\\\_tests/

│   ├── test\\\\\\\_api.py            	← end-to-end pipeline smoke test (3 languages)

│   ├── test\\\\\\\_retrieval.py      	← retrieval smoke test with real queries

│   ├── test\\\\\\\_ingestion.py      	← ingestion smoke test (idempotent via file\\\\\\\_filter)

│   ├── test\\\\\\\_parser\\\\\\\_quick.py   	← single-file parse + ingest smoke test

│   └── test\\\\\\\_rewrite.py        	← query rewriting smoke test (5 cases)

│

└── data/

\\\&#x20;   └── raw/                   	← source documents (PDF, TXT, MD) — not included in repo

\\\\---

## Key Design Decisions

\\\*\\\*Hybrid search over pure vector search\\\*\\\* — lexical search catches exact terms (contract names, article numbers) that semantic search misses. RRF fusion requires no weight calibration.

\\\*\\\*Cohere Rerank over local reranker\\\*\\\* — pyarrow crashes on Python 3.13 + Windows, making local cross-encoders (bge-reranker-v2-m3) uninstallable without downgrading. Cohere API solves this at \\\\\\\~$0.002/query. Migration path documented: rewrite only `reranker.py` when volume exceeds 12,500 queries/month.

\\\*\\\*Gemini 2.5 Flash Lite over Qwen3-8B\\\*\\\* — Qwen3-8B was initially chosen for its strong Arabic comprehension, critical for a predominantly Arabic-speaking rider fleet. Migrated post-testing due to unacceptable latency on OpenRouter. Both models are served via OpenRouter API, keeping future model swaps to a single constant change in llm.py.

\\\*\\\*Single LLM call for language detection + translation\\\*\\\* — replaces the abandoned langdetect approach (structurally fragile on short queries with typos or mixed languages). One Gemini call returns both detected language and English translation as JSON.

\\\*\\\*Conversational memory in browser only\\\*\\\* — 4-turn window stored in session, no DB persistence. Zero privacy risk, zero schema changes.

\\\*\\\*SSE streaming\\\*\\\* — first tokens visible in \\\\\\\~1-2 seconds. Critical for perceived responsiveness.

\\\*\\\*FTS with OR logic instead of AND\\\*\\\* — Postgres `websearch\_to\_tsquery` defaults to AND, which excludes valid chunks whenever the query contains words not present in that chunk. The custom `fts\_search` SQL function builds an explicit OR tsquery, trading precision for recall. Combined with Cohere reranking downstream, recall is cheap and precision is recovered at the rerank step.

\\\\---

## Multilingual Support

\\\* \\\*\\\*Detection + Translation\\\*\\\*: single LLM call returns detected language and English translation as JSON. Query is retrieved in English, answer generated in the rider's original language.
\\\* \\\*\\\*Arabic:\\\*\\\* MSA (Modern Standard Arabic) output. Dialects (Egyptian, Moroccan Darija, Levantine) understood in input, answered in MSA — structural model limitation, not architectural

\\\\---

## Running Locally

```bash
# Clone and install
git clone https://github.com/Kawchee/unofficial\\\\\\\_ue\\\\\\\_chatbot.git
cd unofficial\\\\\\\_ue\\\\\\\_chatbot
python -m venv venv
venv\\\\\\\\Scripts\\\\\\\\activate  # Windows
pip install -r requirements.txt

# Configure environment

\\# Create a .env file in the project root with the following keys:

\\# SUPABASE\\\_URL, SUPABASE\\\_ANON\\\_KEY, SUPABASE\\\_SERVICE\\\_KEY,

\\# OPENAI\\\_API\\\_KEY, OPENROUTER\\\_API\\\_KEY, COHERE\\\_API\\\_KEY
# Start server
uvicorn src.api.app:app --reload --port 8000 --host 0.0.0.0
Open `http://localhost:8000` in your browser.
```

\---

## Deployment

Hosted on Fly.io (Amsterdam). To deploy updates:

```bash
git add .
git commit -m "description"
git push
flyctl deploy
```

\---

## Query Logging

Every query is logged to a `query\_logs` table in Supabase after the response stream completes. Logging never blocks the client — if the insert fails, the error is silently logged server-side and the response is unaffected.

Each row contains:

|Field|Content|
|-|-|
|`query\_original`|Raw user query in their language|
|`query\_english`|Translated query used for retrieval|
|`query\_rewritten`|Rewritten query for conversational context|
|`detected\_language`|Language detected by the LLM|
|`chunks\_retrieved`|File, section, and rerank score for each chunk|
|`response`|Full generated response|

Useful for identifying documentation gaps: queries where `response` contains "I don't have this information" or where retrieved chunks have low rerank scores.

To clear logs manually: `TRUNCATE TABLE query\_logs;`

Automatic cleanup via pg\_cron (runs every Sunday at midnight, deletes rows older than 90 days):

```sql
CREATE EXTENSION IF NOT EXISTS pg\_cron;
SELECT cron.schedule('cleanup-query-logs', '0 0 \* \* 0', $$DELETE FROM query\_logs WHERE created\_at < now() - INTERVAL '90 days'$$);
```

Verify: `SELECT \* FROM cron.job;` — check runs: `SELECT \* FROM cron.job\_run\_details ORDER BY start\_time DESC LIMIT 10;`

\---

## Limitations

* **Missing information:** if a document hasn't been ingested, the system correctly says "I don't have this information" rather than hallucinating.
* **Legal disclaimer:** the CAO is binding in its Dutch text. English version is a translation for convenience.

\---

## Cost Estimate (at full scale — 110k queries/month)

|Component|Cost/month|
|-|-|
|Gemini 2.5 Flash Lite (LLM)|\~$40|
|OpenAI embeddings|<$1|
|bge-reranker-v2-m3|\~$10|
|Fly.io hosting|\~$4|
|**Total**|**\~$55**|

\---

*Built as a learning project exploring production RAG architecture. Contact: unofficial.uechatbot.assistanc@gmail.com*

