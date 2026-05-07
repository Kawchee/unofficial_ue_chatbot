from src.ingestion.pipeline import ingest_all

language_map = {
    "Arbeidsovereenkomst_RAG.md": "nl",
    "Uitzendbevestiging_RAG.md": "nl",
    "Verzuimprotocol.txt": "nl",
    "wegenverkeerswet_1994_civil_liability_NL.txt": "nl",
    "wegenverkeerswet_1994_definitions_algemeen_NL.txt": "nl",
    "wegenverkeerswet_1994_vehicle_use_NL.txt": "nl",
    "uber_user_terms_NL_EN.md": "nl",
    "general_notes_IT.md": "it",
}

results = ingest_all("data/raw", language_map=language_map)