import hashlib
import re
from typing import Any
from uuid import UUID, uuid5

from app.core.security_guardrails import scrub_sensitive_information
from app.db.models import DocumentChunk

MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP = 100

ATX_HEADER = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
CODE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def split_by_headers(text: str) -> list[tuple[list[str], str]]:
    """Split markdown at ATX headers (``#`` to ``######``), ignoring ``#`` lines inside code fences.

    Returns ``(header_path, section_text)`` pairs in document order. ``header_path`` lists the
    enclosing headers including the section's own; text before the first header gets ``[]``.
    """
    sections: list[tuple[list[str], str]] = []
    stack: list[tuple[int, str]] = []
    path: list[str] = []
    current: list[str] = []
    fence: tuple[str, int] | None = None

    def flush() -> None:
        body = "".join(current).strip()
        if body:
            sections.append((path, body))

    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        fence_match = CODE_FENCE.match(stripped)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif (
                marker[0] == fence[0]
                and len(marker) >= fence[1]
                and not fence_match.group(2).strip()
            ):
                fence = None
        elif fence is None:
            header = ATX_HEADER.match(stripped)
            if header:
                flush()
                level = len(header.group(1))
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, header.group(2).strip()))
                path = [title for _, title in stack if title]
                current = [line]
                continue
        current.append(line)
    flush()
    return sections


def find_chunk_start(full_text: str, chunk_content: str, search_from: int = 0) -> int:
    """Char offset of chunk_content's first non-empty line at/after search_from, or -1."""
    first_line = next((ln.strip() for ln in chunk_content.splitlines() if ln.strip()), "")
    if not first_line:
        return -1
    idx = full_text.find(first_line, search_from)
    return idx if idx != -1 else full_text.find(first_line)


def _line_span(full_text: str, chunk_content: str, idx: int) -> tuple[int, int]:
    """1-indexed (start, end) lines of ``chunk_content`` found at char offset ``idx`` (-1 if not found)."""
    if idx == -1:
        return 1, max(1, chunk_content.count("\n") + 1)
    start_line = full_text.count("\n", 0, idx) + 1
    return start_line, start_line + chunk_content.count("\n")


def compute_line_positions(
    full_text: str, chunk_content: str, search_from: int = 0
) -> tuple[int, int]:
    """Find 1-indexed start and end line numbers of chunk_content inside full_text."""
    if not chunk_content or not full_text:
        return 1, 1
    return _line_span(
        full_text, chunk_content, find_chunk_start(full_text, chunk_content, search_from)
    )


def split_large_section(
    section_text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split section text exceeding max_chars by paragraphs/lines while respecting boundaries."""
    if len(section_text) <= max_chars:
        return [section_text]

    chunks: list[str] = []
    lines = section_text.splitlines(keepends=True)
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        # If single line itself exceeds max_chars, flush current chunk and split line with overlap
        if len(line) > max_chars:
            if current_chunk:
                combined = "".join(current_chunk).strip()
                if combined:
                    chunks.append(combined)
                current_chunk = []
                current_len = 0

            step = max(1, max_chars - overlap)
            for idx in range(0, len(line), step):
                slice_part = line[idx : idx + max_chars].strip()
                if slice_part:
                    chunks.append(slice_part)
            continue

        if current_len + len(line) > max_chars and current_chunk:
            combined = "".join(current_chunk).strip()
            if combined:
                chunks.append(combined)

            # Keep overlap lines if possible
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current_chunk):
                if overlap_len + len(prev_line) <= overlap:
                    overlap_lines.insert(0, prev_line)
                    overlap_len += len(prev_line)
                else:
                    break
            current_chunk = overlap_lines
            current_len = overlap_len

        current_chunk.append(line)
        current_len += len(line)

    if current_chunk:
        combined = "".join(current_chunk).strip()
        if combined:
            chunks.append(combined)

    return chunks if chunks else [section_text[:max_chars]]


class MarkdownHierarchicalParser:
    """Markdown parser: splits at headers, then size-limits each section into chunk records."""

    def __init__(self, max_chunk_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP):
        self.max_chunk_chars = max_chunk_chars
        self.overlap = overlap

    @staticmethod
    def _locate(full_text: str, sub_text: str, cursor: int) -> tuple[int, int, int]:
        """Return (start_line, end_line, next_cursor) for a chunk, searching once from cursor."""
        idx = find_chunk_start(full_text, sub_text, cursor)
        start_line, end_line = _line_span(full_text, sub_text, idx)
        return start_line, end_line, idx + 1 if idx != -1 else cursor

    def parse_markdown(
        self,
        markdown_text: str,
        document_id: UUID,
        extra_metadata: dict[str, Any] | None = None,
        chunk_id_namespace: UUID | None = None,
    ) -> list[DocumentChunk]:
        """
        Parse raw markdown content into structured, hierarchical DocumentChunk models.
        Extracts header hierarchy, start_line, end_line, char_count, token_count, and SHA-256 hash.
        With ``chunk_id_namespace`` chunk ids are deterministic (``uuid5(namespace, chunk_index)``),
        so re-parsing the same document keeps stored citations valid.
        """
        extra_metadata = extra_metadata or {}
        clean_text = scrub_sensitive_information(markdown_text, preserve_lines=True)
        if not clean_text.strip():
            return []

        chunks: list[DocumentChunk] = []
        cursor = 0  # chunks arrive in document order; never match a line before the last chunk

        for headers, section_text in split_by_headers(clean_text):
            for sub_text in split_large_section(
                section_text, max_chars=self.max_chunk_chars, overlap=self.overlap
            ):
                start_l, end_l, cursor = self._locate(clean_text, sub_text, cursor)
                meta = {
                    "headerPath": headers,
                    "startLine": start_l,
                    "endLine": end_l,
                    "charCount": len(sub_text),
                    "tokenCount": max(1, len(sub_text.split())),
                    "sha256": hashlib.sha256(sub_text.encode("utf-8")).hexdigest(),
                    **extra_metadata,
                }
                chunk_index = len(chunks)
                chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    content=sub_text,
                    metadata=meta,
                )
                if chunk_id_namespace is not None:
                    chunk.id = uuid5(chunk_id_namespace, str(chunk_index))
                chunks.append(chunk)

        return chunks


default_markdown_parser = MarkdownHierarchicalParser()
