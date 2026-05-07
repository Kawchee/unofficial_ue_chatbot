import re


def chunk_markdown(parsed_doc: dict, max_chunk_size: int = 1000) -> list[dict]:
    """
    Divide il testo Markdown in chunk semantici usando i titoli
    come separatori naturali.

    Args:
        parsed_doc: output della funzione parse_pdf
        max_chunk_size: dimensione massima in caratteri per chunk
                        (chunk più lunghi vengono suddivisi ulteriormente)

    Returns:
        lista di dizionari, ognuno rappresenta un chunk con metadati
    """
    text = parsed_doc["text"]
    file_name = parsed_doc["file_name"]
    page_map = parsed_doc["page_map"]

    # Divide il testo sui titoli Markdown (## o ###)
    # Il pattern cattura il titolo e tutto il testo fino al titolo successivo
    pattern = r'(#{1,3}\s+.+?)(?=#{1,3}\s+|\Z)'
    sections = re.findall(pattern, text, re.DOTALL)

    # Se il documento non ha titoli Markdown, trattalo come un unico blocco
    if not sections:
        sections = [text]

    chunks = []
    chunk_index = 0

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Estrai il titolo della sezione (prima riga)
        lines = section.split('\n')
        title_line = lines[0].strip()
        # Rimuovi simboli Markdown dal titolo per i metadati
        section_title = re.sub(r'^#+\s+|\*\*', '', title_line).strip()

        # Se il chunk è dentro il limite di dimensione, salvalo direttamente
        if len(section) <= max_chunk_size:
            chunks.append({
                "content": section,
                "metadata": {
                    "file_name": file_name,
                    "chunk_index": chunk_index,
                    "page_number": _find_page(chunk_index, len(chunks), page_map),
                    "section_title": section_title
                }
            })
            chunk_index += 1

        # Altrimenti suddividi per paragrafi
        else:
            paragraphs = section.split('\n\n')
            current_chunk = ""

            for para in paragraphs:
                if len(current_chunk) + len(para) <= max_chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk.strip():
                        chunks.append({
                            "content": current_chunk.strip(),
                            "metadata": {
                                "file_name": file_name,
                                "chunk_index": chunk_index,
                                "page_number": _find_page(chunk_index, len(chunks), page_map),
                                "section_title": section_title
                            }
                        })
                        chunk_index += 1
                    current_chunk = para + "\n\n"

            if current_chunk.strip():
                chunks.append({
                    "content": current_chunk.strip(),
                    "metadata": {
                        "file_name": file_name,
                        "chunk_index": chunk_index,
                        "page_number": _find_page(chunk_index, len(chunks), page_map),
                        "section_title": section_title
                    }
                })
                chunk_index += 1

    return chunks


def _find_page(chunk_index: int, total_chunks: int, page_map: list) -> int:
    """
    Stima il numero di pagina per un chunk basandosi sulla
    sua posizione relativa nel documento.
    """
    if not page_map:
        return 1
    if total_chunks == 0:
        return page_map[0]["page_number"]

    # Distribuisce i chunk proporzionalmente tra le pagine
    ratio = chunk_index / max(total_chunks, 1)
    page_index = min(int(ratio * len(page_map)), len(page_map) - 1)
    return page_map[page_index]["page_number"]