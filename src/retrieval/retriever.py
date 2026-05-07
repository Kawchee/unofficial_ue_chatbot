import os
import re
from dotenv import load_dotenv
from supabase import create_client
from src.ingestion.embedder import embed_texts

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)


def _sanitize_for_fts(query: str) -> str:
    cleaned = re.sub(r"[^\w\s']", " ", query)

    stopwords = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "what", "when", "where", "who", "why",
        "how", "which", "that", "this", "these", "those", "i", "you", "he",
        "she", "it", "we", "they", "my", "your", "his", "her", "our", "their",
        "if", "then", "else", "of", "in", "on", "at", "to", "for", "with",
        "from", "by", "about", "as", "and", "or", "but", "not", "no"
    }

    words = [
        w for w in cleaned.lower().split()
        if w and w not in stopwords
    ]

    return " ".join(words)


def vector_search(query: str, top_k: int = 20, timing_collector: dict = None) -> list[dict]:
    """Ricerca semantica via cosine similarity."""
    from src.diagnostics.timing import timed
    from contextlib import nullcontext

    def maybe_timed(name):
        if timing_collector is not None:
            return timed(name, timing_collector)
        return nullcontext()

    with maybe_timed("embed_query"):
        query_embedding = embed_texts([query])[0]

    with maybe_timed("vector_search_db"):
        result = supabase.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": top_k
            }
        ).execute()

    return result.data


def fts_search(query: str, top_k: int = 20, timing_collector: dict = None) -> list[dict]:
    """Ricerca lessicale via Full-Text Search Postgres."""
    from src.diagnostics.timing import timed
    from contextlib import nullcontext

    def maybe_timed(name):
        if timing_collector is not None:
            return timed(name, timing_collector)
        return nullcontext()

    sanitized = _sanitize_for_fts(query)

    if not sanitized:
        return []

    with maybe_timed("fts_search_db"):
        result = supabase.rpc(
            "fts_search",
            {
                "query_text": sanitized,
                "match_count": top_k
            }
        ).execute()

    return result.data


def hybrid_search(query: str, top_k: int = 20, k: int = 60, timing_collector: dict = None) -> list[dict]:
    """Hybrid search con RRF."""
    candidates_pool = max(top_k * 2, 20)
    vec_results = vector_search(query, top_k=candidates_pool, timing_collector=timing_collector)
    fts_results = fts_search(query, top_k=candidates_pool, timing_collector=timing_collector)

    rrf_scores = {}
    chunk_data = {}

    for rank, chunk in enumerate(vec_results):
        chunk_id = chunk["id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)
        chunk_data[chunk_id] = chunk

    for rank, chunk in enumerate(fts_results):
        chunk_id = chunk["id"]
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)
        if chunk_id not in chunk_data:
            chunk_data[chunk_id] = chunk

    sorted_ids = sorted(
        rrf_scores.keys(),
        key=lambda cid: rrf_scores[cid],
        reverse=True
    )

    final_results = []
    for chunk_id in sorted_ids[:top_k]:
        chunk = chunk_data[chunk_id]
        chunk["rrf_score"] = rrf_scores[chunk_id]
        final_results.append(chunk)

    return final_results


def search(query: str, top_k: int = 5, candidates: int = 20, timing_collector: dict = None) -> list[dict]:
    """
    Funzione finale di retrieval — punto d'ingresso del sistema.
    """
    from src.retrieval.reranker import rerank

    candidates_chunks = hybrid_search(query, top_k=candidates, timing_collector=timing_collector)

    if not candidates_chunks:
        return []

    from src.diagnostics.timing import timed
    from contextlib import nullcontext

    def maybe_timed(name):
        if timing_collector is not None:
            return timed(name, timing_collector)
        return nullcontext()

    with maybe_timed("rerank"):
        final_chunks = rerank(query, candidates_chunks, top_k=top_k)

    return final_chunks
