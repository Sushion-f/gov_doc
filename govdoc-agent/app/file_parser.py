"""Parse uploaded workspace files to plain text + simple HTML (docx / pdf / text)."""

from __future__ import annotations

from html import escape
from pathlib import Path


def _text_to_html(text: str) -> str:
    safe = escape((text or "")[:50000])
    return f"<pre>{safe}</pre>"


def parse_uploaded_file(filename: str, content: bytes) -> tuple[str, str]:
    """
    Returns (content_text, content_html) for workspace storage.
    """
    ext = Path(filename or "file").suffix.lower()
    if ext == ".docx":
        return _parse_docx(content)
    if ext == ".pdf":
        return _parse_pdf(content)
    if ext in {".txt", ".md", ".markdown", ".json", ".csv"}:
        text = _decode_utf8(content)
        return text[:100000], _text_to_html(text[:50000])
    return _decode_utf8(content)[:100000], _text_to_html(_decode_utf8(content)[:50000])


def _decode_utf8(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")


def _parse_docx(content: bytes) -> tuple[str, str]:
    try:
        from io import BytesIO

        from docx import Document
    except ImportError:
        text = _decode_utf8(content)[:10000]
        return text, _text_to_html(text)

    try:
        doc = Document(BytesIO(content))
        parts: list[str] = []
        for para in doc.paragraphs:
            line = (para.text or "").strip()
            if line:
                parts.append(line)
        text = "\n".join(parts) or _decode_utf8(content)[:10000]
    except Exception:
        text = _decode_utf8(content)[:10000]
    text = text[:100000]
    return text, _text_to_html(text[:50000])


def _parse_pdf(content: bytes) -> tuple[str, str]:
    try:
        from io import BytesIO

        import pdfplumber
    except ImportError:
        text = _decode_utf8(content)[:10000]
        return text, _text_to_html(text)

    parts: list[str] = []
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages[:80]:
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(t.strip())
        text = "\n\n".join(parts) if parts else _decode_utf8(content)[:10000]
    except Exception:
        text = _decode_utf8(content)[:10000]
    text = text[:100000]
    return text, _text_to_html(text[:50000])
