# Smoke test — parsing e ingestione di un singolo PDF.
#
# Scopo: verificare che il parser PDF e la pipeline di ingestione
# funzionino end-to-end su un file reale.
#
# Effetti collaterali: inserisce il documento in Supabase.
# Se il documento è già presente, verrà duplicato — eseguire con consapevolezza.
# Per rimuovere il documento inserito usare check_db.py o cleanup_and_reingest.py.
#
# Uso: python tests/test_parser_quick.py

from src.ingestion.pipeline import ingest_file

result = ingest_file("data/raw/Deactivation notice FAQs.pdf", language="en")

print()
print("=== RIEPILOGO ===")
print(f"Document ID: {result['document_id']}")
print(f"File: {result['file_name']}")
print(f"Pagine: {result['total_pages']}")
print(f"Chunk salvati: {result['chunks_saved']}")
