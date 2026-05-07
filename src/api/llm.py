import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# OpenRouter usa lo stesso client di OpenAI
# cambia solo base_url e il nome del modello
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

MODEL = "google/gemini-2.5-flash-lite"

DETECT_AND_TRANSLATE_PROMPT = """You are a language detection and translation assistant.

Given a query, you must return a JSON object with exactly two fields:
- "language": the ISO 639-1 code of the query language (e.g. "it", "ar", "nl", "en", "fr", "tr")
- "english_query": the query translated to English (if already English, return it unchanged)

Rules:
- Return ONLY the JSON object. No explanations, no markdown, no extra text.
- For Arabic, always use "ar" regardless of dialect (Egyptian, Moroccan, Gulf, etc.)
- If unsure about the language, default to "en"

Examples:
Query: "Come vengono calcolate le mie holiday?"
Response: {"language": "it", "english_query": "How are my holidays calculated?"}

Query: "كيفاش كيتحسب لأجر ديالي؟"
Response: {"language": "ar", "english_query": "How is my salary calculated?"}

Query: "What is my hourly wage?"
Response: {"language": "en", "english_query": "What is my hourly wage?"}"""


def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1
) -> str:
    """
    Chiama Gemini 2.5 Flash Lite via OpenRouter e restituisce la risposta testuale.

    Args:
        system_prompt: istruzione permanente che definisce il comportamento
        user_message: messaggio dell'utente (domanda + contesto)
        temperature: 0.1 = risposte conservative e precise (ideale per RAG)

    Returns:
        testo della risposta del modello
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        max_tokens=1000,
    )

    return response.choices[0].message.content


def detect_and_translate(query: str) -> dict:
    """
    Rileva la lingua della query e la traduce in inglese in una sola chiamata.

    Args:
        query: domanda del rider in qualsiasi lingua

    Returns:
        dizionario con:
        - language: codice ISO 639-1 della lingua rilevata (es. "it", "ar", "nl")
        - english_query: query tradotta in inglese (invariata se già inglese)

    Fallback: se la risposta non è JSON valido, restituisce lingua "en"
    e query originale — safe default che non blocca la pipeline.
    """
    raw = call_llm(
        system_prompt=DETECT_AND_TRANSLATE_PROMPT,
        user_message=query,
        temperature=0.0
    ).strip()

    try:
        # Rimuove eventuali backtick markdown se il modello li aggiunge
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

        # Verifica che i campi attesi siano presenti
        if "language" in result and "english_query" in result:
            return result
        else:
            raise ValueError("Missing fields in JSON response")

    except (json.JSONDecodeError, ValueError):
        # Fallback sicuro: inglese, query originale
        return {"language": "en", "english_query": query}


def rewrite_query(
    history: list[tuple[str, str]],
    current_english_query: str
) -> str:
    """
    Riscrive la query corrente come stringa autonoma in inglese,
    usando la cronologia conversazionale come contesto per il retrieval.

    Come funziona:
    - Se la cronologia è vuota, ritorna la query invariata (niente da contestualizzare).
    - Se la query è già autonoma o il topic è cambiato, il modello la ritorna invariata.
    - Altrimenti produce una query arricchita con il contesto necessario.

    L'output va direttamente all'hybrid search — deve essere in inglese
    perché i chunk del corpus sono prevalentemente in inglese.

    Args:
        history: lista di tuple (user_message_originale, assistant_response_originale).
                 Le ultime N tuple rappresentano i turni recenti della conversazione.
                 I messaggi possono essere in qualsiasi lingua — il rewriter
                 è istruito a produrre output in inglese indipendentemente.
        current_english_query: query corrente già tradotta in inglese
                               da detect_and_translate().

    Returns:
        stringa in inglese pronta per il retrieval.
        Fallback: current_english_query invariata se la chiamata fallisce.
    """
    from src.api.prompt import REWRITE_PROMPT  # import locale per evitare circolarità

    # Se non c'è storia, non c'è niente da contestualizzare
    if not history:
        return current_english_query

    # Costruisce il blocco history leggibile per il modello
    history_lines = []
    for user_msg, assistant_msg in history:
        history_lines.append(f"User: {user_msg}")
        history_lines.append(f"Assistant: {assistant_msg}")
    history_text = "\n".join(history_lines)

    user_message = f"""History:
{history_text}

Current query (translated): {current_english_query}
Rewritten query:"""

    raw = call_llm(
        system_prompt=REWRITE_PROMPT,
        user_message=user_message,
        temperature=0.0  # deterministico: vogliamo riformulazione, non creatività
    ).strip()

    # Fallback: se il modello restituisce stringa vuota o solo whitespace
    if not raw:
        return current_english_query

    return raw
