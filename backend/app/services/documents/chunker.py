from typing import List, Dict, Any, Tuple


class TextChunker:
    """Splits document text into overlapping chunks with metadata preservation."""

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, pages: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
        chunks = []
        global_idx = 0

        for page_num, text in pages:
            if not text.strip():
                continue

            start = 0
            text_len = len(text)

            while start < text_len:
                end = start + self.chunk_size
                chunk_text = text[start:end]

                # Refine break to nearest sentence or word boundary if possible
                if end < text_len:
                    last_period = chunk_text.rfind(". ")
                    last_newline = chunk_text.rfind("\n")
                    break_point = max(last_period + 1, last_newline)
                    if break_point > self.chunk_size // 2:
                        chunk_text = chunk_text[:break_point]
                        start += break_point
                    else:
                        start += self.chunk_size - self.chunk_overlap
                else:
                    start = text_len

                cleaned = chunk_text.strip()
                if len(cleaned) >= 15:  # Avoid trivial fragments
                    chunks.append({
                        "chunk_index": global_idx,
                        "page_number": page_num,
                        "content": cleaned,
                    })
                    global_idx += 1

        return chunks
