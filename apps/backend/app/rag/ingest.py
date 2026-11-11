"""Document ingestion with LlamaIndex: PDF or Markdown -> DocumentChunk rows."""

import io
from uuid import UUID, uuid5

from llama_index.core import Document as LIDocument
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from pypdf import PdfReader

from app.core.security_guardrails import scrub_sensitive_information
from app.db.models import DocumentChunk

_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
_markdown = MarkdownNodeParser()


def _pdf_documents(data: bytes, filename: str) -> list[LIDocument]:
    reader = PdfReader(io.BytesIO(data))
    docs = []
    for i, page in enumerate(reader.pages, start=1):
        text = scrub_sensitive_information(page.extract_text() or "")
        if text.strip():
            docs.append(LIDocument(text=text, metadata={"filename": filename, "page": i}))
    return docs


def build_chunks(
    data: bytes,
    filename: str,
    document_id: UUID,
    chunk_id_namespace: UUID | None = None,
) -> list[DocumentChunk]:
    if filename.lower().endswith(".pdf"):
        nodes = _splitter.get_nodes_from_documents(_pdf_documents(data, filename))
    else:
        text = scrub_sensitive_information(data.decode("utf-8-sig"), preserve_lines=True)
        md_nodes = _markdown.get_nodes_from_documents(
            [LIDocument(text=text, metadata={"filename": filename})]
        )
        nodes = _splitter(md_nodes)  # split oversized sections
    chunks = []
    for _index, node in enumerate(nodes):
        content = node.get_content().strip()
        if not content:
            continue
        header = node.metadata.get("header_path", "")
        meta = {
            "filename": filename,
            "headerPath": [h for h in str(header).split("/") if h],
            "page": node.metadata.get("page"),
        }
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=len(chunks),
            content=content,
            metadata=meta,
        )
        if chunk_id_namespace is not None:
            chunk.id = uuid5(chunk_id_namespace, str(chunk.chunk_index))
        chunks.append(chunk)
    return chunks
