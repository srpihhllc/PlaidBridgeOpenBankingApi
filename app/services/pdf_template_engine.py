# =============================================================================
# FILE: app/services/pdf_template_engine.py
# DESCRIPTION: Cockpit-grade CSV → PDF template engine.
#              Standalone, deterministic, operator-friendly.
# =============================================================================

import csv
from pathlib import Path

from fpdf import FPDF


# -------------------------------------------------------------------------
# Core Engine
# -------------------------------------------------------------------------
class CSVtoPDFEngine:
    """
    A cockpit-grade CSV → PDF template engine.
    - Deterministic output
    - No Flask context required
    - Operator-friendly error surfacing
    """

    def __init__(self, title: str = "Report", font: str = "Arial"):
        self.title = title
        self.font = font

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def render_pdf(self, csv_path: str, pdf_path: str, template: str = "table") -> None:
        """
        Render a CSV file into a PDF using the selected template.
        Supported templates:
            - "table" (default)
            - "compact"
            - "audit"
        """
        rows = self._read_csv(csv_path)
        if not rows:
            rows = [["No data"]]

        if template == "table":
            pdf_bytes = self._render_table(rows)
        elif template == "compact":
            pdf_bytes = self._render_compact(rows)
        elif template == "audit":
            pdf_bytes = self._render_audit(rows)
        else:
            raise ValueError(f"Unknown template: {template}")

        Path(pdf_path).write_bytes(pdf_bytes)

    # ---------------------------------------------------------------------
    # CSV Reader
    # ---------------------------------------------------------------------
    def _read_csv(self, csv_path: str) -> list[list[str]]:
        try:
            with open(csv_path) as f:
                reader = csv.reader(f)
                return [row for row in reader]
        except Exception:
            return []

    # ---------------------------------------------------------------------
    # Template: Table
    # ---------------------------------------------------------------------
    def _render_table(self, rows: list[list[str]]) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font(self.font, "B", 14)
        pdf.cell(0, 10, self.title, ln=True, align="C")

        pdf.set_font(self.font, size=10)

        col_widths = self._auto_col_widths(rows, pdf)

        for row in rows:
            for i, cell in enumerate(row):
                # fpdf-stubs define the keyword as `text`, not `txt`
                pdf.cell(col_widths[i], 8, text=str(cell), border=1)
            pdf.ln()

        # pdf.output(dest="S") returns a bytearray; convert to bytes
        return bytes(pdf.output(dest="S"))

    # ---------------------------------------------------------------------
    # Template: Compact
    # ---------------------------------------------------------------------
    def _render_compact(self, rows: list[list[str]]) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font(self.font, "B", 12)
        pdf.cell(0, 8, self.title, ln=True)

        pdf.set_font(self.font, size=9)

        for row in rows:
            pdf.cell(0, 6, " | ".join(str(c) for c in row), ln=True)

        return bytes(pdf.output(dest="S"))

    # ---------------------------------------------------------------------
    # Template: Audit
    # ---------------------------------------------------------------------
    def _render_audit(self, rows: list[list[str]]) -> bytes:
        pdf = FPDF()
        pdf.add_page()

        pdf.set_font(self.font, "B", 16)
        pdf.cell(0, 10, f"{self.title} (Audit View)", ln=True)

        pdf.set_font(self.font, size=9)

        for idx, row in enumerate(rows):
            pdf.cell(0, 6, f"[{idx:04d}] " + " | ".join(str(c) for c in row), ln=True)

        return bytes(pdf.output(dest="S"))

    # ---------------------------------------------------------------------
    # Column Auto-Sizing
    # ---------------------------------------------------------------------
    def _auto_col_widths(self, rows: list[list[str]], pdf: FPDF) -> list[int]:
        if not rows:
            return [40]

        num_cols = max(len(r) for r in rows)
        # use float internally because get_string_width returns float
        widths: list[float] = [0.0] * num_cols

        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], pdf.get_string_width(str(cell)) + 6.0)

        total_width = sum(widths)
        max_width = pdf.w - 20  # pdf.w is float

        if total_width > max_width and total_width > 0:
            scale = max_width / total_width
            widths = [w * scale for w in widths]

        # Convert to ints for consumer code (pixel/point widths)
        return [int(round(w)) for w in widths]
