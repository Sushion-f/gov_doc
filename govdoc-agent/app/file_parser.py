"""Parse workspace files to plain text + HTML and persist metadata through storage cache helpers."""

from __future__ import annotations

import re
import zipfile
from html import escape
from io import BytesIO
from pathlib import Path


def _text_to_html(text: str) -> str:
    safe = escape((text or "")[:50000])
    return f"<pre>{safe}</pre>"


def _decode_utf8(content: bytes) -> str:
    return content.decode("utf-8", errors="ignore")


_HTML_SNIFF_HEAD = re.compile(rb"^\s*(<!doctype\s+html|<html[\s>]|<head[\s>]|<body[\s>])", re.IGNORECASE)
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[\s\S]*?</\1>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"[ \t]+")
_MULTINL_RE = re.compile(r"\n{3,}")
_CLOUDFLARE_MARKERS = ("cf_chl_opt", "/cdn-cgi/challenge-platform", "Just a moment...")


def _looks_like_html(content: bytes) -> bool:
    """粗判：前若干字节像 HTML/XML 起始，或含 HTML 特征标签。"""
    head = content[:4096]
    if _HTML_SNIFF_HEAD.search(head):
        return True
    low = head.lower()
    return b"<html" in low or b"<body" in low or b"<!doctype" in low


def _html_to_readable_text(raw_html: str) -> str:
    """把错误 HTML 清成纯文本，去掉 script/style，合并空白。"""
    text = _SCRIPT_STYLE_RE.sub(" ", raw_html or "")
    text = _TAG_RE.sub(" ", text)
    text = text.replace("&nbsp;", " ")
    text = _MULTISPACE_RE.sub(" ", text)
    text = _MULTINL_RE.sub("\n\n", text)
    return text.strip()


def _corrupted_doc_html(
    *,
    filename: str,
    reason: str,
    preview_text: str,
) -> str:
    """渲染一张可视化的"文件无法解析"提示卡，避免直接倾泻原始 HTML/二进制。"""
    safe_name = escape(filename or "未知文件")
    safe_reason = escape(reason)
    safe_preview = escape((preview_text or "").strip()[:4000]) or "（无文本内容）"
    return (
        "<div class=\"corrupted-doc-card\" "
        "style=\"border:1px solid #f5c2c2;background:#fff6f6;padding:16px 18px;"
        "border-radius:8px;color:#9b1c1c;font-family:inherit;line-height:1.6;\">"
        f"<p style=\"margin:0 0 8px;font-weight:600;\">⚠️ 无法解析该文件：{safe_name}</p>"
        f"<p style=\"margin:0 0 10px;color:#6b2a2a;\">{safe_reason}</p>"
        "<details style=\"margin-top:8px;\"><summary style=\"cursor:pointer;color:#3b3b3b;\">"
        "查看原始文本预览（已去除脚本与样式）</summary>"
        f"<pre style=\"margin-top:8px;white-space:pre-wrap;color:#333;background:#fff;"
        f"padding:10px 12px;border-radius:6px;max-height:320px;overflow:auto;\">{safe_preview}</pre>"
        "</details></div>"
    )


def _detect_corrupted_reason(filename: str, content: bytes) -> str | None:
    """如果扩展名是 docx/pdf 但内容明显是 HTML / 反爬页，返回人类可读原因。"""
    ext = Path(filename or "").suffix.lower()
    if ext not in {".docx", ".pdf", ".xlsx", ".pptx"}:
        return None
    if not _looks_like_html(content):
        return None
    snippet = content[:8192].decode("utf-8", errors="ignore")
    if any(marker in snippet for marker in _CLOUDFLARE_MARKERS):
        return (
            "文件扩展名标记为 "
            f"{ext or '二进制'}，但内容实际上是 Cloudflare 验证页 / 反爬拦截 HTML。"
            "通常是下载链接需要登录或被风控，请重新导出原始文档后再上传。"
        )
    return (
        f"文件扩展名为 {ext or '二进制'}，但内容是 HTML 页面，无法按该格式解析。"
        "可能是下载途中被错误页替换，请重新导出真实文档后再上传。"
    )


def _detect_format(filename: str, content: bytes) -> str:
    ext = Path(filename or "file").suffix.lower()
    if ext in {
        ".docx",
        ".pdf",
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".csv",
        ".xlsx",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".gif",
        ".webp",
    }:
        return ext
    if content.startswith(b"%PDF"):
        return ".pdf"
    if content.startswith(b"\x89PNG") or content.startswith(b"\xff\xd8"):
        return ".image"
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return ext or ".txt"
    if any(name.startswith("word/") for name in names):
        return ".docx"
    if any(name.startswith("xl/") for name in names):
        return ".xlsx"
    if any(name.startswith("ppt/") for name in names):
        return ".pptx"
    return ext or ".txt"


def parse_uploaded_file(filename: str, content: bytes) -> tuple[str, str]:
    parsed = parse_file_bytes(filename, content)
    return parsed["content_text"], parsed["content_html"]


def parse_file_path(path: Path) -> dict:
    return parse_file_bytes(path.name, path.read_bytes())


def parse_file_bytes(filename: str, content: bytes) -> dict:
    # 扩展名宣称是文档/表格但内容实际是 HTML（常见于被 Cloudflare/登录页拦截后保存下来），
    # 直接走一张"损坏文件"提示卡，避免把 HTML 原样倾泻进编辑器。
    corrupted_reason = _detect_corrupted_reason(filename, content)
    if corrupted_reason:
        raw_html = _decode_utf8(content)
        preview_text = _html_to_readable_text(raw_html)
        ext = Path(filename or "").suffix.lower().lstrip(".") or "binary"
        return {
            "content_text": (preview_text or "")[:100000],
            "content_html": _corrupted_doc_html(
                filename=filename,
                reason=corrupted_reason,
                preview_text=preview_text,
            ),
            "meta": {"parser": f"{ext}-corrupted-html", "pages": 1, "corrupted": True, "reason": corrupted_reason},
        }

    file_type = _detect_format(filename, content)
    if file_type == ".docx":
        content_text, content_html, meta = _parse_docx(filename, content)
    elif file_type == ".pdf":
        content_text, content_html, meta = _parse_pdf(filename, content)
    elif file_type == ".xlsx":
        content_text, content_html, meta = _parse_xlsx(content)
    elif file_type == ".pptx":
        content_text, content_html, meta = _parse_pptx(content)
    elif file_type in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".image"}:
        content_text, content_html, meta = _parse_image(filename)
    else:
        text = _decode_utf8(content)[:100000]
        content_text, content_html, meta = text, _text_to_html(text[:50000]), {"parser": "text", "pages": 1}
    return {
        "content_text": content_text[:100000],
        "content_html": content_html,
        "meta": meta,
    }


def _parse_docx(filename: str, content: bytes) -> tuple[str, str, dict]:
    text = ""
    html = ""
    parser = "docx-fallback"
    docx_ok = False
    mammoth_ok = False
    try:
        from docx import Document

        doc = Document(BytesIO(content))
        parts = [(para.text or "").strip() for para in doc.paragraphs]
        text = "\n".join(item for item in parts if item)
        parser = "python-docx"
        docx_ok = True
    except Exception:
        pass

    try:
        import mammoth

        result = mammoth.convert_to_html(BytesIO(content))
        if result.value:
            html = result.value
            parser = "mammoth"
            mammoth_ok = True
    except Exception:
        pass

    if not docx_ok and not mammoth_ok:
        # 两条真解析链都失败了：文件大概率不是合法 docx。
        # 用一张"损坏文件"提示卡替代之前裸字节 <pre> 的丑陋兜底。
        raw_text = _decode_utf8(content)
        if _looks_like_html(content):
            reason = "该文件扩展名为 .docx，但内容实际为 HTML 页面（可能是下载时被登录/验证页替换），请重新导出真实 docx 后再上传。"
            preview = _html_to_readable_text(raw_text)
        else:
            reason = "python-docx 与 mammoth 都无法解析该文件，可能已损坏或并非合法的 DOCX。"
            preview = raw_text[:4000]
        return (
            preview[:100000],
            _corrupted_doc_html(filename=filename, reason=reason, preview_text=preview),
            {"parser": "docx-corrupted", "pages": 1, "corrupted": True, "reason": reason},
        )

    if not html:
        html = _text_to_html(text[:50000])
    return text[:100000], html, {"parser": parser, "pages": max(1, text.count("\n\n") + 1)}


def _parse_pdf(filename: str, content: bytes) -> tuple[str, str, dict]:
    pages = 1
    parser = "pdf-fallback"
    text = ""
    ok = False
    try:
        import pdfplumber

        parts: list[str] = []
        with pdfplumber.open(BytesIO(content)) as pdf:
            pages = len(pdf.pages) or 1
            for page in pdf.pages[:80]:
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(t.strip())
        text = "\n\n".join(parts) if parts else ""
        parser = "pdfplumber"
        ok = True
    except Exception:
        pass

    if not ok:
        raw_text = _decode_utf8(content)
        if _looks_like_html(content):
            reason = "该文件扩展名为 .pdf，但内容实际为 HTML 页面（可能是下载时被登录/验证页替换），请重新导出真实 PDF 后再上传。"
            preview = _html_to_readable_text(raw_text)
        else:
            reason = "pdfplumber 无法打开该文件，可能已损坏或并非合法 PDF。"
            preview = raw_text[:4000]
        return (
            preview[:100000],
            _corrupted_doc_html(filename=filename, reason=reason, preview_text=preview),
            {"parser": "pdf-corrupted", "pages": 1, "corrupted": True, "reason": reason},
        )
    return text[:100000], _text_to_html(text[:50000]), {"parser": parser, "pages": pages}


def _parse_xlsx(content: bytes) -> tuple[str, str, dict]:
    text = _decode_utf8(content)[:10000]
    html = _text_to_html(text[:50000])
    sheet_count = 1
    parser = "xlsx-fallback"
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(content), data_only=True)
        blocks: list[str] = []
        html_blocks: list[str] = []
        sheet_count = len(workbook.sheetnames) or 1
        for sheet in workbook.worksheets:
            rows: list[str] = []
            html_rows: list[str] = []
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if not any(values):
                    continue
                rows.append("\t".join(values))
                html_cells = "".join(f"<td>{escape(value)}</td>" for value in values)
                html_rows.append(f"<tr>{html_cells}</tr>")
            if rows:
                blocks.append(f"[{sheet.title}]\n" + "\n".join(rows))
                html_blocks.append(
                    f"<section><h3>{escape(sheet.title)}</h3><table>{''.join(html_rows)}</table></section>"
                )
        if blocks:
            text = "\n\n".join(blocks)
            html = "".join(html_blocks)
            parser = "openpyxl"
    except Exception:
        pass
    return text[:100000], html, {"parser": parser, "pages": sheet_count}


def _parse_pptx(content: bytes) -> tuple[str, str, dict]:
    text = _decode_utf8(content)[:10000]
    html = _text_to_html(text[:50000])
    slide_count = 1
    parser = "pptx-fallback"
    try:
        from pptx import Presentation

        deck = Presentation(BytesIO(content))
        slide_count = len(deck.slides) or 1
        blocks: list[str] = []
        html_blocks: list[str] = []
        for index, slide in enumerate(deck.slides, start=1):
            lines: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    value = str(shape.text or "").strip()
                    if value:
                        lines.append(value)
            if lines:
                body = "\n".join(lines)
                blocks.append(f"[Slide {index}]\n{body}")
                html_blocks.append(
                    f"<section><h3>Slide {index}</h3><pre>{escape(body)}</pre></section>"
                )
        if blocks:
            text = "\n\n".join(blocks)
            html = "".join(html_blocks)
            parser = "python-pptx"
    except Exception:
        pass
    return text[:100000], html, {"parser": parser, "pages": slide_count}


def _parse_image(filename: str) -> tuple[str, str, dict]:
    text = f"[OCR 占位] 当前暂不解析图片正文：{filename}"
    return text, _text_to_html(text), {"parser": "image-placeholder", "pages": 1}
