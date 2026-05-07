import pymupdf4llm
from pathlib import Path


def parse_pdf(pdf_path: str) -> dict:
    """
    Parsa un PDF e restituisce testo Markdown strutturato
    con metadati del documento.

    Args:
        pdf_path: percorso al file PDF

    Returns:
        dizionario con testo markdown e metadati
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {pdf_path}")

    if not path.suffix.lower() == ".pdf":
        raise ValueError(f"Il file non è un PDF: {pdf_path}")

    pages = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=True
    )

    full_text = ""
    page_map = []

    for page in pages:
        page_start = len(full_text)
        full_text += page["text"] + "\n\n"
        page_map.append({
            "page_number": page["metadata"]["page_number"],
            "char_start": page_start,
            "char_end": len(full_text)
        })

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "total_pages": len(pages),
        "text": full_text,
        "page_map": page_map
    }