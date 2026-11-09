import os
import io
import csv
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple
import pypdf


class DocumentExtractor:
    """Extracts text content and page/section metadata from various file formats."""

    @classmethod
    def extract(cls, file_bytes: bytes, filename: str) -> List[Tuple[int, str]]:
        """
        Extract text from file bytes.
        Returns a list of tuples: (page_or_section_number, text_content).
        """
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".pdf":
            return cls._extract_pdf(file_bytes)
        elif ext == ".docx":
            return cls._extract_docx(file_bytes)
        elif ext in [".txt", ".md", ".json", ".py", ".js", ".ts", ".html", ".css", ".sql"]:
            return cls._extract_plain_text(file_bytes)
        elif ext == ".csv":
            return cls._extract_csv(file_bytes)
        else:
            # Fallback to UTF-8 decoded text
            return cls._extract_plain_text(file_bytes)

    @classmethod
    def _extract_pdf(cls, file_bytes: bytes) -> List[Tuple[int, str]]:
        results = []
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            cleaned = text.strip()
            if cleaned:
                results.append((page_idx, cleaned))
        return results

    @classmethod
    def _extract_docx(cls, file_bytes: bytes) -> List[Tuple[int, str]]:
        paragraphs = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx_zip:
                xml_content = docx_zip.read("word/document.xml")
                root = ET.fromstring(xml_content)
                # WordprocessingML namespace
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for p in root.findall(".//w:p", ns):
                    p_text = "".join(node.text for node in p.findall(".//w:t", ns) if node.text)
                    if p_text.strip():
                        paragraphs.append(p_text.strip())
        except Exception:
            # Fallback
            paragraphs.append(file_bytes.decode("utf-8", errors="ignore"))

        full_text = "\n\n".join(paragraphs)
        return [(1, full_text)] if full_text.strip() else []

    @classmethod
    def _extract_plain_text(cls, file_bytes: bytes) -> List[Tuple[int, str]]:
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        return [(1, text)] if text else []

    @classmethod
    def _extract_csv(cls, file_bytes: bytes) -> List[Tuple[int, str]]:
        text = file_bytes.decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(text))
        rows = [", ".join(row) for row in reader if row]
        return [(1, "\n".join(rows))] if rows else []
