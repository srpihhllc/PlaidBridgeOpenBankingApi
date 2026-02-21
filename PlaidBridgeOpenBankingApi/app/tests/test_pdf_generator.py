# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_pdf_generator.py

from pathlib import Path

from app.services.pdf_generator import (
    _minimal_markdown_to_text,
    build_pdf,
    render_pdf_from_markdown,
)


def test_minimal_markdown_to_text_basic():
    md = "# Title\n\nSome text.\n\n- Item 1\n- Item 2"
    out = _minimal_markdown_to_text(md)
    assert "Title" in out
    assert "- Item 1" in out


def test_build_pdf_creates_file(tmp_path):
    lines = ["Hello", "World"]
    export_dir = tmp_path / "exports"
    meta = build_pdf(lines, title="Test", export_dir=str(export_dir))

    assert "filename" in meta
    assert Path(meta["filepath"]).exists()


def test_render_pdf_from_markdown(tmp_path):
    md = "# Header\n\nSome content."
    export_dir = tmp_path / "exports"
    meta = render_pdf_from_markdown(md, title="Doc", export_dir=str(export_dir))

    assert Path(meta["filepath"]).exists()
