import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from src.ingestion.parser import parse_pdf
from src.ingestion.parser_text import parse_text
from src.ingestion.chunker import chunk_markdown
from src.ingestion.embedder import embed_texts

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}
MIN_CHUNK_LENGTH = 10


def clean_text(text):
    if not isinstance(text, str):
        return text
    return text.replace("\x00", "")


def is_valid_chunk(content):
    if not content:
        return False
    return len(content.strip()) >= MIN_CHUNK_LENGTH


def cleanup_old_documents(file_filter):
    """
    Cancella da Supabase tutti i documenti (e i loro chunk) il cui nome
    corrisponde a uno dei file in file_filter.

    Viene chiamata automaticamente da ingest_all() quando file_filter
    è specificato, prima di reinserire i dati aggiornati.

    Args:
        file_filter: lista di nomi file (es. ['FAQ.txt', 'guida_busta_paga.pdf'])
    """
    print("=" * 50)
    print("CLEANUP DOCUMENTI VECCHI")
    print("=" * 50)

    docs_result = supabase.table("documents").select("id, name").execute()
    all_docs = docs_result.data

    docs_to_delete = [doc["id"] for doc in all_docs if doc["name"] in file_filter]

    if not docs_to_delete:
        print("Nessun documento da pulire.\n")
        return

    print("Trovati " + str(len(docs_to_delete)) + " documento/i da eliminare.")

    for doc_id in docs_to_delete:
        supabase.table("chunks").delete().eq("document_id", doc_id).execute()
        print("  Chunk eliminati per documento: " + str(doc_id))

    for doc_id in docs_to_delete:
        supabase.table("documents").delete().eq("id", doc_id).execute()
        print("  Documento eliminato: " + str(doc_id))

    print("Cleanup completato.\n")


def ingest_file(file_path, language="en"):
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Formato non supportato: " + ext)
    print("Inizio ingestione: " + path.name)
    print("  [1/4] Parsing...")
    if ext == ".pdf":
        parsed = parse_pdf(file_path)
    else:
        parsed = parse_text(file_path)
    print("         " + str(parsed["total_pages"]) + " pagine, " + str(len(parsed["text"])) + " caratteri")
    print("  [2/4] Chunking...")
    chunks = chunk_markdown(parsed)
    print("         " + str(len(chunks)) + " chunk prodotti")
    valid_chunks = []
    skipped_count = 0
    for chunk in chunks:
        cleaned_content = clean_text(chunk["content"])
        if is_valid_chunk(cleaned_content):
            chunk["content"] = cleaned_content
            valid_chunks.append(chunk)
        else:
            skipped_count += 1
    if skipped_count > 0:
        print("         " + str(skipped_count) + " chunk vuoti/degenerati saltati")
        print("         " + str(len(valid_chunks)) + " chunk validi rimasti")
    if len(valid_chunks) == 0:
        print("  ATTENZIONE: nessun chunk valido prodotto, file saltato.")
        return {
            "document_id": None,
            "file_name": path.name,
            "total_pages": parsed["total_pages"],
            "chunks_saved": 0,
            "skipped": True
        }
    print("  [3/4] Salvataggio documento in Supabase...")
    doc_result = supabase.table("documents").insert({
        "name": clean_text(parsed["file_name"]),
        "source_type": "pdf" if ext == ".pdf" else "text",
        "language": language,
        "metadata": {
            "total_pages": parsed["total_pages"],
            "file_path": clean_text(parsed["file_path"]),
            "format": ext
        }
    }).execute()
    document_id = doc_result.data[0]["id"]
    print("         ID documento: " + str(document_id))
    print("  [4/4] Calcolo embedding e salvataggio chunk...")
    texts = [chunk["content"] for chunk in valid_chunks]
    embeddings = embed_texts(texts)
    rows = []
    for chunk, embedding in zip(valid_chunks, embeddings):
        rows.append({
            "document_id": document_id,
            "content": chunk["content"],
            "embedding": embedding,
            "chunk_index": chunk["metadata"]["chunk_index"],
            "metadata": {
                "section_title": clean_text(chunk["metadata"]["section_title"]),
                "page_number": chunk["metadata"]["page_number"],
                "file_name": clean_text(chunk["metadata"]["file_name"])
            }
        })
    supabase.table("chunks").insert(rows).execute()
    print("         " + str(len(rows)) + " chunk salvati")
    print("  Completato.\n")
    return {
        "document_id": document_id,
        "file_name": path.name,
        "total_pages": parsed["total_pages"],
        "chunks_saved": len(rows),
        "skipped": False
    }


def ingest_all(folder_path, language_map=None, file_filter=None):
    # Se file_filter è specificato, cancella prima tutti i documenti vecchi
    # corrispondenti — evita duplicati nel database
    if file_filter is not None:
        cleanup_old_documents(file_filter)

    folder = Path(folder_path)
    files = [f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    if file_filter is not None:
        files = [f for f in files if f.name in file_filter]
    if not files:
        print("Nessun file supportato trovato in " + folder_path)
        return []
    print("Trovati " + str(len(files)) + " file da ingestare.\n")
    if language_map is None:
        language_map = {}
    results = []
    for f in sorted(files):
        lang = language_map.get(f.name, "en")
        try:
            result = ingest_file(str(f), language=lang)
            results.append(result)
        except Exception as e:
            print("  ERRORE su " + f.name + ": " + str(e) + "\n")
            results.append({"file_name": f.name, "error": str(e), "skipped": True})
    success = [r for r in results if not r.get("skipped") and not r.get("error")]
    skipped = [r for r in results if r.get("skipped")]
    errors = [r for r in results if r.get("error")]
    print("=" * 50)
    print("RIEPILOGO INGESTIONE MASSIVA")
    print("=" * 50)
    print("Completati: " + str(len(success)))
    print("Saltati:    " + str(len(skipped)))
    print("Errori:     " + str(len(errors)))
    print("Chunk totali salvati: " + str(sum(r.get("chunks_saved", 0) for r in success)))
    if errors:
        print("\nFile con errori:")
        for r in errors:
            print("  - " + r["file_name"] + ": " + r["error"])
    return results