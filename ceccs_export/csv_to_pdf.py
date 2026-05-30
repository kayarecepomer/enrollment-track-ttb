"""
Convert a courses CSV (from export_courses.py) to a PDF table.

Usage:
    python csv_to_pdf.py output/courses_20265_all.csv
    python csv_to_pdf.py output/courses_20265_all.csv --out my_report.pdf
"""

import argparse
import csv
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

COLS = [
    ("full_code",       "Code",         28),
    ("title",           "Title",        62),
    ("faculty_code",    "Faculty",      18),
    ("department_name", "Department",   52),
    ("instructors",     "Instructor(s)",52),
    ("total_enrollment","Enrol",        16),
    ("total_capacity",  "Cap",          13),
    ("delivery_mode",   "Mode",         18),
]

HEADER_H  = 7
ROW_H     = 5
MAX_CHARS = 38


def sanitize(text: str) -> str:
    """Replace common Unicode characters that latin-1 fonts can't encode."""
    replacements = {
        "—": "-", "–": "-",   # em/en dash
        "‘": "'", "’": "'",   # curly single quotes
        "“": '"', "”": '"',   # curly double quotes
        "…": "...",                # ellipsis
        " ": " ",                  # non-breaking space
        "•": "*",                  # bullet
        "·": "*",                  # middle dot
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def truncate(text: str, n: int = MAX_CHARS) -> str:
    text = sanitize(text)
    return text if len(text) <= n else text[: n - 1] + "~"


def csv_to_pdf(csv_path: str, pdf_path: str) -> None:
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_margins(8, 8, 8)
    pdf.add_page()

    # ── title ──────────────────────────────────────────────────────────────
    session = rows[0].get("session", "") if rows else ""
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(
        0, 9,
        f"UofT Course Enrollment - session {session}  ({len(rows)} courses)",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 7)
    pdf.cell(0, 4, csv_path, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    # ── column headers ──────────────────────────────────────────────────────
    pdf.set_fill_color(30, 80, 160)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 7)
    for _, label, w in COLS:
        pdf.cell(w, HEADER_H, label, border=1, fill=True)
    pdf.ln()

    # ── rows ────────────────────────────────────────────────────────────────
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 6.5)
    for i, row in enumerate(rows):
        fill = i % 2 == 0
        pdf.set_fill_color(240, 245, 255) if fill else pdf.set_fill_color(255, 255, 255)
        for key, _, w in COLS:
            pdf.cell(w, ROW_H, truncate(row.get(key, "")), border=1, fill=fill)
        pdf.ln()

    pdf.output(pdf_path)
    print(f"Saved {len(rows)} rows -> {pdf_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="Path to the CSV file")
    parser.add_argument("--out", help="Output PDF path (default: same name as CSV)")
    args = parser.parse_args()

    out = args.out or os.path.splitext(args.csv)[0] + ".pdf"
    csv_to_pdf(args.csv, out)


if __name__ == "__main__":
    main()
