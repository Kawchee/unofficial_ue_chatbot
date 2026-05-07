import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    Calcola gli embedding per una lista di testi.
    Processa in batch per rispettare i limiti API di OpenAI.

    Args:
        texts: lista di stringhe da vettorializzare
        batch_size: quanti testi mandare per chiamata API

    Returns:
        lista di vettori (ogni vettore è una lista di 1536 float)
    """
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        response = client.embeddings.create(
            input=batch,
            model="text-embedding-3-small"
        )

        # Ordina per indice per garantire che l'ordine sia preservato
        batch_embeddings = sorted(
            response.data,
            key=lambda x: x.index
        )
        all_embeddings.extend([e.embedding for e in batch_embeddings])

    return all_embeddings