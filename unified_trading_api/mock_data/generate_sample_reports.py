"""Generate sample PDF reports for mock/demo mode.

Produces minimal valid PDF files for executive reports and PnL attribution
without external dependencies (fpdf2, reportlab, etc.).
"""

from __future__ import annotations

from pathlib import Path


def _pdf_escape(text: str) -> str:
    """Escape special PDF characters in text strings."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(pages: list[list[str]]) -> bytes:
    """Build a minimal valid PDF from a list of pages (each page = list of lines)."""
    objects: list[str] = []

    # Object 1: Catalog
    objects.append("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")

    # Object 2: Pages
    page_refs = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"2 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {len(pages)} >>\nendobj")

    # Font object (shared)
    font_obj_num = 3 + len(pages) * 2
    objects_for_pages: list[str] = []

    for i, page_lines in enumerate(pages):
        page_obj_num = 3 + i * 2
        content_obj_num = 4 + i * 2

        # Build content stream
        text_ops: list[str] = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
        for line in page_lines:
            escaped = _pdf_escape(line)
            text_ops.append(f"({escaped}) '")
        text_ops.append("ET")
        stream = "\n".join(text_ops)

        # Content object
        objects_for_pages.append(
            f"{content_obj_num} 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj"
        )

        # Page object
        objects_for_pages.append(
            f"{page_obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 612 792] "
            f"/Contents {content_obj_num} 0 R "
            f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
            f">>\nendobj"
        )

    # Font object
    font_obj = f"{font_obj_num} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj"

    all_objects = objects + objects_for_pages + [font_obj]

    # Build PDF
    lines: list[str] = ["%PDF-1.4"]
    offsets: list[int] = []
    for obj in all_objects:
        offsets.append(len("\n".join(lines)) + 1)
        lines.append(obj)

    xref_offset = len("\n".join(lines)) + 1
    total_objects = len(all_objects) + 1  # +1 for free entry
    lines.append("xref")
    lines.append(f"0 {total_objects}")
    lines.append("0000000000 65535 f ")
    for off in offsets:
        lines.append(f"{off:010d} 00000 n ")

    lines.append("trailer")
    lines.append(f"<< /Size {total_objects} /Root 1 0 R >>")
    lines.append("startxref")
    lines.append(str(xref_offset))
    lines.append("%%EOF")

    return ("\n".join(lines) + "\n").encode("latin-1")


def generate_executive_report() -> bytes:
    """Generate a sample executive report PDF."""
    return _build_pdf(
        [
            [
                "# Executive Report",
                "",
                "Period: 2026-04-01 to 2026-04-16",
                "",
                "## Portfolio Summary",
                "Total AUM: $12.5M",
                "Net P&L: +$342,100 (+2.7%)",
                "Sharpe Ratio: 2.1",
                "",
                "## Strategy Performance",
                "DeFi Basis: +$180K",
                "CeFi Momentum: +$95K",
                "Sports Arb: +$67K",
            ],
        ]
    )


def generate_pnl_attribution() -> bytes:
    """Generate a sample PnL attribution report PDF."""
    return _build_pdf(
        [
            [
                "# PnL Attribution Report",
                "",
                "## Attribution Breakdown",
                "Trading PnL: +$215,000",
                "Funding PnL: +$89,000",
                "Staking Yield: +$45,000",
                "Transaction Costs: -$6,900",
                "",
                "## Reconciliation",
                "Total PnL: $342,100",
                "Attributed: $342,100",
                "Unexplained: $0 (0.00%)",
            ],
        ]
    )


if __name__ == "__main__":
    out_dir = Path(__file__).parent / "sample_reports"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "executive_report.pdf").write_bytes(generate_executive_report())
    (out_dir / "pnl_attribution.pdf").write_bytes(generate_pnl_attribution())
