import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from src.api.prompt import SYSTEM_PROMPT
from src.api.pipeline import (
    extract_history_and_query,
    build_context,
    build_user_message,
    MAX_HISTORY_TURNS,
)
from src.api.llm import detect_and_translate, rewrite_query, MODEL
from src.retrieval.retriever import search

load_dotenv()

# Configura il logger per questo modulo.
# Il livello effettivo è controllato dalla variabile d'ambiente LOG_LEVEL.
# Default: WARNING (i messaggi DEBUG non appaiono in produzione).
# Per attivare il debug: LOG_LEVEL=DEBUG uvicorn src.api.app:app ...
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "WARNING").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS — permette al frontend di chiamare il backend
# anche se serviti da indirizzi diversi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Client OpenRouter per streaming.
# Il nome del modello (MODEL) è definito in llm.py e importato da lì,
# così esiste un'unica source of truth per tutta la pipeline.
openrouter_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)


class Message(BaseModel):
    role: str    # "user" o "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


def validate_messages(messages: list[Message]) -> list[dict]:
    """
    Valida e normalizza la lista messaggi ricevuta dal frontend.

    Controlli:
    - Lista non vuota
    - Ultimo messaggio deve essere role="user"
    - Contenuto ultimo messaggio non vuoto
    - Troncamento server-side agli ultimi MAX_HISTORY_TURNS turni + ultima query

    Returns:
        lista di dict normalizzati [{"role": ..., "content": ...}]

    Raises:
        HTTPException 400 se la lista non è valida
    """
    if not messages:
        raise HTTPException(status_code=400, detail="Empty messages list")

    msgs = [{"role": m.role, "content": m.content} for m in messages]

    if msgs[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")

    last_content = msgs[-1]["content"].strip()
    if not last_content:
        raise HTTPException(status_code=400, detail="Last user message is empty")

    # Troncamento server-side: mantieni gli ultimi MAX_HISTORY_TURNS turni completi
    # (MAX_HISTORY_TURNS * 2 messaggi) + l'ultima query utente
    max_messages = MAX_HISTORY_TURNS * 2 + 1
    if len(msgs) > max_messages:
        msgs = msgs[-max_messages:]

    return msgs


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Endpoint principale del chatbot.
    Riceve la lista messaggi e restituisce la risposta in streaming (SSE).

    Formato richiesta:
        {"messages": [{"role": "user", "content": "..."}, ...]}

    Formato risposta (stream SSE):
        data: {"type": "sources", "sources": [...]}
        data: {"type": "token", "content": "..."}
        data: {"type": "done"}
    """
    # Step 1 — Valida e normalizza i messaggi
    msgs = validate_messages(request.messages)

    # Step 2 — Estrai history e ultima query
    history, last_query = extract_history_and_query(msgs)

    # Step 3 — Rileva lingua e traduci in inglese
    detection = detect_and_translate(last_query)
    detected_lang = detection["language"]
    english_query = detection["english_query"]
    logger.debug("lang=%s | english_query=%s", detected_lang, english_query)

    # Step 4 — Riscrive la query contestualizzandola con la history
    retrieval_query = rewrite_query(history, english_query)
    logger.debug("retrieval_query=%s", retrieval_query)

    # Step 5 — Retrieval sulla query riscritta
    chunks = search(retrieval_query, top_k=5)

    # Step 6 — Assembla contesto e messaggio
    context = build_context(chunks)
    user_message = build_user_message(last_query, context, detected_lang, history)
    logger.debug("user_message tail:\n%s", user_message[-300:])

    # Step 7 — Estrai fonti (deduplicate per file)
    sources = []
    seen = set()
    for chunk in chunks:
        key = chunk["metadata"].get("file_name", "")
        if key not in seen:
            seen.add(key)
            sources.append({
                "file": chunk["metadata"].get("file_name", "Unknown"),
                "section": chunk["metadata"].get("section_title", "Unknown"),
            })

    # Step 8 — Streaming della risposta
    def generate():
        # Invia le fonti prima di iniziare lo stream del testo
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        stream = openrouter_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1,
            max_tokens=1000,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield f"data: {json.dumps({'type': 'token', 'content': delta.content})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@app.get("/health")
async def health():
    """Endpoint di verifica — conferma che il server è attivo."""
    return {"status": "ok"}


# Serve il frontend in modalità sviluppo locale.
# Avviando uvicorn dalla root del progetto, questa riga rende il frontend
# raggiungibile direttamente su http://localhost:8000 senza un server separato.
# In un deployment di produzione il frontend verrebbe servito in modo indipendente
# (es. Nginx, CDN) e questa riga non sarebbe necessaria.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
