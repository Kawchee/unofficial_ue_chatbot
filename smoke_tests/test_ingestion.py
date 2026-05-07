# Smoke test — ingestione massiva di un sottoinsieme di documenti.
#
# Scopo: verificare che la pipeline di ingestione funzioni end-to-end
# su file di tipo diverso (PDF, TXT, MD) con language_map.
#
# Idempotenza: questo script usa file_filter, il che attiva il cleanup
# automatico in ingest_all() — i documenti elencati vengono eliminati
# da Supabase prima di essere reinseriti. Può essere eseguito più volte
# senza creare duplicati.
#
# Effetti collaterali: consuma crediti API (OpenAI embedding).
# I documenti elencati in FILE_FILTER verranno sovrascritti in Supabase.
#
# Per aggiungere o rimuovere file dal test, modificare FILE_FILTER.
#
# Uso: python tests/test_ingestion.py

from src.ingestion.pipeline import ingest_all

LANGUAGE_MAP = {
    "wegenverkeerswet_1994_civil_liability_NL.txt": "nl",
    "wegenverkeerswet_1994_definitions_algemeen_NL.txt": "nl",
    "wegenverkeerswet_1994_vehicle_use_NL.txt": "nl",
    "Uitzendbevestiging_RAG.md": "nl",
}

# Sottoinsieme rappresentativo: un PDF, un TXT, un MD.
# Modificare questa lista per testare file specifici.
FILE_FILTER = [
    "FAQ.txt",
    "CAO voor Uitzendkrachten 2026-2028 Engels.pdf",
    "Uitzendbevestiging_RAG.md",
]

results = ingest_all("data/raw", language_map=LANGUAGE_MAP, file_filter=FILE_FILTER)
