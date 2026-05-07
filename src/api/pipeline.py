import logging
from src.retrieval.retriever import search
from src.api.llm import call_llm, detect_and_translate, rewrite_query
from src.api.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "it": "Italian",
    "ar": "Arabic",
    "nl": "Dutch",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "tr": "Turkish",
    "ro": "Romanian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
}

MAX_HISTORY_TURNS = 4


def extract_history_and_query(messages: list[dict]) -> tuple[list[tuple[str, str]], str]:
    if not messages:
        return [], ""

    last_query = messages[-1]["content"]
    preceding = messages[:-1]

    pairs = []
    i = len(preceding) - 1
    while i >= 1 and len(pairs) < MAX_HISTORY_TURNS:
        if preceding[i]["role"] == "assistant" and preceding[i-1]["role"] == "user":
            pairs.append((preceding[i-1]["content"], preceding[i]["content"]))
            i -= 2
        else:
            i -= 1

    pairs.reverse()
    return pairs, last_query


def build_context(chunks: list[dict]) -> str:
    if not chunks:
        return "No relevant documents found."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        file_name = chunk["metadata"].get("file_name", "Unknown")
        section = chunk["metadata"].get("section_title", "Unknown section")
        content = chunk["content"]
        context_parts.append(
            f"[Document {i}]\n"
            f"Source: {file_name}\n"
            f"Section: {section}\n"
            f"Content:\n{content}"
        )

    return "\n\n---\n\n".join(context_parts)


def build_history_text(history: list[tuple[str, str]]) -> str:
    if not history:
        return ""

    lines = []
    for user_msg, assistant_msg in history:
        lines.append(f"User: {user_msg}")
        lines.append(f"Assistant: {assistant_msg}")

    return "\n".join(lines)


def build_user_message(
    query: str,
    context: str,
    detected_lang: str,
    history: list[tuple[str, str]]
) -> str:
    lang_name = LANGUAGE_NAMES.get(detected_lang, detected_lang.upper())
    logger.debug("lang_name resolved to: '%s'", lang_name)
    history_text = build_history_text(history)
    history_section = ""
    if history_text:
        history_section = f"""[Conversation history]
{history_text}
---
"""
    return f"""{history_section}Here are the relevant documents I found for your question:
{context}
---
Question: {query}
Please answer based only on the documents above and the conversation history (if present).
RESPOND IN: {lang_name}"""


def answer(messages: list[dict], top_k: int = 5, timing_collector: dict = None) -> dict:
    """
    Pipeline RAG completa con chiamata LLM bloccante (non streaming).

    NOTA: questa funzione NON è usata dall'endpoint di produzione /chat,
    che usa invece StreamingResponse in app.py per restituire i token
    man mano che vengono generati.
    answer() è usata esclusivamente da scripts/benchmark_ttft.py per
    misurare la latenza di ogni step della pipeline: una chiamata bloccante
    è più semplice da strumentare rispetto a uno stream SSE.

    Args:
        messages: lista messaggi, ultimo deve essere role="user"
        top_k: numero di chunk da recuperare
        timing_collector: se passato, viene popolato con i tempi di ogni step.
                          Struttura: {"step_name": seconds_float, ...}
                          Se None, non viene misurato nulla (comportamento normale).
    """
    from src.diagnostics.timing import timed
    from contextlib import nullcontext

    def maybe_timed(name):
        """Wrapper: usa il timer solo se c'è un collector."""
        if timing_collector is not None:
            return timed(name, timing_collector)
        return nullcontext()

    # Step 1 — Estrai history e ultima query (CPU locale, non misurata)
    history, last_query = extract_history_and_query(messages)

    # Step 2 — Rileva lingua e traduci in inglese
    with maybe_timed("detect_and_translate"):
        detection = detect_and_translate(last_query)
    detected_lang = detection["language"]
    english_query = detection["english_query"]

    # Step 3 — Riscrive la query (no-op se history vuota)
    with maybe_timed("rewrite_query"):
        retrieval_query = rewrite_query(history, english_query)

    # Step 4 — Retrieval (embedding + vector search + fts + rerank)
    with maybe_timed("retrieval_total"):
        chunks = search(retrieval_query, top_k=top_k, timing_collector=timing_collector)

    # Step 5 — Assembla contesto (CPU locale, trascurabile)
    context = build_context(chunks)

    # Step 6 — Assembla messaggio (CPU locale, trascurabile)
    user_message = build_user_message(last_query, context, detected_lang, history)

    # Step 7 — Chiama il modello e misura il time-to-first-token
    with maybe_timed("llm_call_total"):
        response_text = call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message
        )

    # Step 8 — Estrai le fonti
    sources = []
    for chunk in chunks:
        source = {
            "file": chunk["metadata"].get("file_name", "Unknown"),
            "section": chunk["metadata"].get("section_title", "Unknown"),
            "score": chunk.get("rerank_score", 0)
        }
        if source not in sources:
            sources.append(source)

    return {
        "answer": response_text,
        "sources": sources,
        "chunks_used": len(chunks),
        "query_translated": detected_lang != "en",
        "detected_language": detected_lang,
        "rewritten_query": retrieval_query
    }
