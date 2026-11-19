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
        elif ext == ".xlsx":
            return cls._extract_xlsx(file_bytes)
        elif ext in [".txt", ".md", ".json", ".py", ".js", ".ts", ".html", ".css", ".sql", ".yaml", ".yml", ".log"]:
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
        text = file_bytes.decode("utf-8", errors="ignore").replace("\x00", "")
        reader = csv.reader(io.StringIO(text))
        rows = [", ".join(row) for row in reader if any(cell.strip() for cell in row)]
        return [(1, "\n".join(rows))] if rows else []

    @classmethod
    def _extract_xlsx(cls, file_bytes: bytes) -> List[Tuple[int, str]]:
        """Extract rows per worksheet from .xlsx ZIP XML without third-party dependencies."""
        sections: List[Tuple[int, str]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                shared_strings: List[str] = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    for si in ss_root.iter():
                        if si.tag.endswith("}si") or si.tag == "si":
                            parts = [t.text or "" for t in si.iter() if (t.tag.endswith("}t") or t.tag == "t")]
                            shared_strings.append("".join(parts))

                sheet_names: List[str] = []
                if "xl/workbook.xml" in zf.namelist():
                    wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
                    for elem in wb_root.iter():
                        if elem.tag.endswith("}sheet") or elem.tag == "sheet":
                            name = elem.attrib.get("name")
                            if name:
                                sheet_names.append(name)

                sheet_paths = sorted(
                    n for n in zf.namelist()
                    if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
                )
                for idx, path in enumerate(sheet_paths, start=1):
                    root = ET.fromstring(zf.read(path))
                    lines: List[str] = []
                    for row in root.iter():
                        if row.tag.endswith("}row") or row.tag == "row":
                            cells: List[str] = []
                            for c in row:
                                if not (c.tag.endswith("}c") or c.tag == "c"):
                                    continue
                                cell_type = c.attrib.get("t", "")
                                val_text = ""
                                for child in c:
                                    if child.tag.endswith("}v") or child.tag == "v":
                                        val_text = child.text or ""
                                    elif child.tag.endswith("}is") or child.tag == "is":
                                        val_text = "".join(
                                            t.text or "" for t in child.iter()
                                            if t.tag.endswith("}t") or t.tag == "t"
                                        )
                                if cell_type == "s" and val_text.isdigit():
                                    s_idx = int(val_text)
                                    val_text = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else val_text
                                cells.append(val_text.replace("\x00", "").strip())
                            if any(cells):
                                lines.append(" | ".join(cells))
                    if lines:
                        label = sheet_names[idx - 1] if idx - 1 < len(sheet_names) else f"Sheet {idx}"
                        sections.append((idx, f"[Sheet: {label}]\n" + "\n".join(lines)))
        except Exception:
            fallback = file_bytes.decode("utf-8", errors="ignore").replace("\x00", "").strip()
            if fallback:
                sections.append((1, fallback))
        return sections
