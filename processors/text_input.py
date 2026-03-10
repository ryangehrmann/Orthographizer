"""
processors/text_input.py
Read .txt and .docx text files, split into (token, is_khmer) pairs.
"""
import re
import io


# Khmer Unicode block
_KHMER_RE = re.compile(r"[\u1780-\u17FF]+")

# Split on whitespace and paragraph-like breaks; keep delimiters
_SPLIT_RE = re.compile(r"(\s+)")


def _contains_khmer(text: str) -> bool:
    return bool(_KHMER_RE.search(text))


def _split_to_tokens(text: str) -> list[tuple[str, bool]]:
    """
    Split text on whitespace/line breaks into tokens.
    Returns list of (token, is_khmer) tuples, preserving whitespace tokens
    so the caller can reconstruct line structure.
    """
    parts = _SPLIT_RE.split(text)
    tokens = []
    for part in parts:
        if not part:
            continue
        tokens.append((part, _contains_khmer(part)))
    return tokens


def _paragraphs_to_tokens(paragraphs: list[str]) -> list[list[tuple[str, bool]]]:
    """
    Convert a list of paragraph strings to a list of token lists.
    Each inner list = one paragraph.  Empty paragraphs produce an empty list.
    """
    result = []
    for para in paragraphs:
        stripped = para.strip()
        if stripped:
            tokens = _split_to_tokens(stripped)
            result.append(tokens)
        else:
            result.append([])  # blank paragraph → empty line in output
    return result


def read_txt(file_obj) -> tuple[list[list[tuple[str, bool]]] | None, str | None]:
    """
    Read a .txt file.  Attempts UTF-8 first, then falls back to charset-normalizer
    (or latin-1 as a last resort).

    Returns:
        (paragraphs, error) — paragraphs is a list-of-lists of (token, is_khmer).
    """
    raw = file_obj.read()
    if isinstance(raw, str):
        raw = raw.encode("utf-8")

    # Try chardet / charset-normalizer
    text = None
    try:
        from charset_normalizer import from_bytes
        result = from_bytes(raw).best()
        if result is not None:
            text = str(result)
    except ImportError:
        pass

    if text is None:
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue

    if text is None:
        return None, "Could not decode the text file. Try saving it as UTF-8."

    paragraphs = re.split(r"\r?\n", text)
    return _paragraphs_to_tokens(paragraphs), None


def read_docx_text(file_obj) -> tuple[list[list[tuple[str, bool]]] | None, str | None]:
    """
    Read a .docx file and extract paragraph text.

    Returns:
        (paragraphs, error) — paragraphs is a list-of-lists of (token, is_khmer).
    """
    try:
        from docx import Document
    except ImportError:
        return None, "python-docx is not installed. Run: pip install python-docx"

    try:
        doc = Document(file_obj)
    except Exception as e:
        return None, f"Could not open Word document: {e}"

    paragraphs = [p.text for p in doc.paragraphs]
    return _paragraphs_to_tokens(paragraphs), None


def read_text_file(
    file_obj, filename: str
) -> tuple[list[list[tuple[str, bool]]] | None, str | None]:
    """
    Dispatch to the appropriate reader based on filename extension.
    """
    lower = filename.lower()
    if lower.endswith(".docx"):
        return read_docx_text(file_obj)
    elif lower.endswith(".txt"):
        return read_txt(file_obj)
    else:
        return None, f"Unsupported file type: '{filename}'. Please upload a .txt or .docx file."
