# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_pdf_parser.py

from pathlib import Path

from app.services.pdf_parser import parse_pdf


def test_parse_pdf_returns_empty_for_nonexistent_file(tmp_path: Path):
    missing_path = tmp_path / "no_such_file.pdf"
    assert parse_pdf(str(missing_path)) == []


def test_parse_pdf_returns_empty_for_empty_file(tmp_path: Path):
    file_path = tmp_path / "dummy.pdf"
    file_path.write_text("not really a PDF")
    assert parse_pdf(str(file_path)) == []
