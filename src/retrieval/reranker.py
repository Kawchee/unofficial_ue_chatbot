import os
import cohere
from dotenv import load_dotenv

load_dotenv()

# Client Cohere inizializzato una volta sola
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise ValueError("COHERE_API_KEY non trovata nel file .env")
        _client = cohere.ClientV2(api_key=api_key)
    return _client


def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    """
    Riordina i chunk candidati per rilevanza reale usando Cohere Rerank 3.5.

    Args:
        query: domanda dell'utente
        chunks: lista di chunk candidati (output di hybrid_search)
        top_k: numero di chunk da restituire

    Returns:
        lista di chunk ordinati per rilevanza decrescente,
        ognuno con campo 'rerank_score'
    """
    if not chunks:
        return []

    client = _get_client()

    # Costruisce la lista di documenti come semplici stringhe
    documents = [chunk["content"] for chunk in chunks]

    # Chiama Cohere Rerank
    response = client.rerank(
        model="rerank-v3.5",
        query=query,
        documents=documents,
        top_n=top_k
    )

    # La risposta contiene una lista di risultati con:
    # - index: posizione del documento nella lista originale
    # - relevance_score: punteggio di rilevanza [0, 1]
    reranked = []
    for result in response.results:
        original_chunk = chunks[result.index]
        original_chunk["rerank_score"] = float(result.relevance_score)
        reranked.append(original_chunk)

    return reranked