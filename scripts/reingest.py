# scripts/reingest.py
#
# Script di manutenzione per reingestione mirata di documenti specifici.
# Usa questo script quando aggiorni o correggi uno o più file in data/raw/
# e vuoi reinserirli in Supabase senza svuotare l'intero database.
#
# Come usarlo:
#   1. Modifica FILE_FILTER con i nomi esatti dei file da ingestire.
#   2. Se i file sono in olandese o italiano, aggiungi le voci in LANGUAGE_MAP.
#   3. Lancia: python scripts/reingest.py
#
# Comportamento:
#   - I documenti elencati in FILE_FILTER vengono eliminati da Supabase
#     (i chunk vengono rimossi in cascade) e poi reinseriti da zero.
#   - I documenti NON elencati in FILE_FILTER non vengono toccati.
#   - Può essere eseguito più volte senza creare duplicati.
#
# Uso: python scripts/reingest.py

from src.ingestion.pipeline import ingest_all

# --- CONFIGURA QUI ---

# File da ingestire (nomi esatti come appaiono in data/raw/)
FILE_FILTER = [
    # "FAQ.txt",
    # "CAO voor Uitzendkrachten 2026-2028 Engels.pdf",
    # "Uitzendbevestiging_RAG.md",
]

# Lingua per file non-inglesi (ometti i file EN — default è "en")
LANGUAGE_MAP = {
    "wegenverkeerswet_1994_civil_liability_NL.txt": "nl",
    "wegenverkeerswet_1994_definitions_algemeen_NL.txt": "nl",
    "wegenverkeerswet_1994_vehicle_use_NL.txt": "nl",
    "Uitzendbevestiging_RAG.md": "nl",
    # "general_notes_IT.md": "it",  # bilingue IT/EN — lasciato come "en" per compatibilità FTS
}

# --- FINE CONFIGURAZIONE ---

if not FILE_FILTER:
    print("FILE_FILTER è vuoto. Aggiungi i file da ingestire e rilancia.")
else:
    ingest_all("data/raw", language_map=LANGUAGE_MAP, file_filter=FILE_FILTER)
