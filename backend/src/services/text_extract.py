from pathlib import Path


def extract_text(file_path: str) -> str:
    """Extract text from a PDF or DOCX file."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in (".pdf", ".docx"):
        raise ValueError(f"Unsupported file type: {suffix}")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if suffix == ".pdf":
        return _extract_pdf(path)
    else:
        return _extract_docx(path)


def _extract_pdf(path: Path) -> str:
    import pymupdf

    text_parts = []
    with pymupdf.open(str(path)) as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _extract_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
