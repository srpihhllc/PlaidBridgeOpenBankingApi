# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_csv_utils.py

import csv
import io
import json
from pathlib import Path

import pytest

from app.services.csv_utils import export_csv, import_csv

SAMPLE_DATA = [
    {"date": "2024-01-01", "description": "Coffee Shop", "amount": "-5.50"},
    {"date": "2024-01-02", "description": "Salary Deposit", "amount": "1500.00"},
    {"date": "2024-01-03", "description": "Rent", "amount": "-800.00"},
]


def test_csv_export_writes_expected_data(tmp_path: Path):
    output_file = tmp_path / "export.csv"
    data_copy = json.loads(json.dumps(SAMPLE_DATA))

    # FIX: pass file path as keyword argument
    export_csv(data_copy, output_path=str(output_file))
    assert output_file.exists()

    read_back: list[dict[str, str]] = []
    with open(output_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        read_back.extend(reader)

    assert read_back == SAMPLE_DATA


def test_csv_export_creates_empty_file_for_empty_data(tmp_path: Path):
    output_file = tmp_path / "empty.csv"
    export_csv([], output_path=str(output_file))

    assert output_file.exists()
    assert output_file.stat().st_size == 0


def test_csv_import_reads_expected_data(tmp_path: Path):
    input_file = tmp_path / "input.csv"
    buffer = io.StringIO()

    writer = csv.DictWriter(buffer, fieldnames=list(SAMPLE_DATA[0].keys()))
    writer.writeheader()
    writer.writerows(SAMPLE_DATA)

    input_file.write_text(buffer.getvalue(), encoding="utf-8")

    imported = import_csv(str(input_file))
    assert imported == SAMPLE_DATA


def test_csv_import_returns_empty_for_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.csv"
    result = import_csv(str(missing))
    assert result == []


def test_csv_import_returns_empty_for_empty_file(tmp_path: Path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")

    result = import_csv(str(empty_file))
    assert result == []


@pytest.mark.parametrize(
    "bad_content",
    [
        "not,csv,at,all",
        "a,b,c\n1,2",
        "foo\nbar\nbaz",
        "extra,columns,here\n1,2,3,4",
    ],
)
def test_csv_import_handles_malformed_csv(tmp_path: Path, bad_content):
    fpath = tmp_path / "malformed.csv"
    fpath.write_text(bad_content, encoding="utf-8")

    result = import_csv(str(fpath))
    assert isinstance(result, list)
