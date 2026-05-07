# Smoke test — pipeline RAG completa (detect → rewrite → retrieval → LLM).
#
# Scopo: verificare che answer() risponda correttamente a query in lingue diverse,
# rilevando la lingua e restituendo una risposta coerente.
#
# Nota: answer() è la pipeline bloccante usata dal benchmark, non dall'endpoint
# di produzione /chat (che usa streaming SSE). Il comportamento RAG è identico.
#
# Effetti collaterali: consuma crediti API (OpenAI embedding, OpenRouter LLM, Cohere rerank).
#
# Uso: python tests/test_api.py

import time
from src.api.pipeline import answer

queries = [
    "What are metrics and how do they work?",
    "Cosa devo fare se sono malato e non posso lavorare?",
    "ماذا يجب أن أفعل إذا كنت مريضاً ولا أستطيع العمل؟",
]

for query in queries:
    print(f"\n{'=' * 60}")
    print(f"QUERY: {query}")
    print("=" * 60)

    start = time.time()
    result = answer(messages=[{"role": "user", "content": query}])
    elapsed = time.time() - start

    print(f"Lingua rilevata: {result['detected_language']}")
    print(f"Tradotta: {result['query_translated']}")
    print(f"Query riscritta: {result['rewritten_query']}")
    print(f"Chunk usati: {result['chunks_used']}")
    print(f"Tempo totale: {elapsed:.1f}s")
    print()
    print(result["answer"])
    print()
