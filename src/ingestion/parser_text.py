from pathlib import Path


def parse_text(file_path: str) -> dict:
    """
    Legge un file TXT o MD e restituisce il contenuto
    con la stessa struttura di output di parse_pdf.

    Args:
        file_path: percorso al file TXT o MD

    Returns:
        dizionario compatibile con chunk_markdown()
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {file_path}")

    if path.suffix.lower() not in [".txt", ".md"]:
        raise ValueError(f"Formato non supportato: {path.suffix}")

    text = path.read_text(encoding="utf-8")

    # Struttura identica all'output di parse_pdf
    # page_map ha una sola voce — i file TXT/MD non hanno pagine
    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "total_pages": 1,
        "text": text,
        "page_map": [
            {
                "page_number": 1,
                "char_start": 0,
                "char_end": len(text)
            }
        ]
    }