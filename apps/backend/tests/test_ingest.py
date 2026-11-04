import io
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.rag.ingest import build_chunks


def _create_sample_pdf(text: str = "Sample benchmark evaluation results.") -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 100 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = stream
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_markdown_ingest_preserves_header_path():
    doc_id = uuid4()
    markdown_content = (
        b"# MMLU Benchmark\n\n"
        b"Introduction to general language understanding.\n\n"
        b"## Performance\n\n"
        b"Overview of performance across categories.\n\n"
        b"### Metrics\n\n"
        b"State of the art models achieve over 90% accuracy."
    )

    chunks = build_chunks(markdown_content, "mmlu.md", doc_id)
    assert len(chunks) >= 2
    paths = [c.metadata["headerPath"] for c in chunks]
    assert any("MMLU Benchmark" in p for p in paths)
    assert any("Performance" in p for p in paths)
    assert all(c.metadata["filename"] == "mmlu.md" for c in chunks)
    assert all(c.metadata["page"] is None for c in chunks)


def test_pdf_ingest_records_page_number():
    doc_id = uuid4()
    pdf_bytes = _create_sample_pdf("SWE-bench evaluates software engineering capability.")

    chunks = build_chunks(pdf_bytes, "swe_bench.pdf", doc_id)
    assert len(chunks) == 1
    assert "SWE-bench" in chunks[0].content
    assert chunks[0].metadata["page"] == 1
    assert chunks[0].metadata["filename"] == "swe_bench.pdf"


def test_empty_input_returns_empty_chunks():
    doc_id = uuid4()
    assert build_chunks(b"", "empty.md", doc_id) == []
    assert build_chunks(b"   \n\n   ", "whitespace.md", doc_id) == []
