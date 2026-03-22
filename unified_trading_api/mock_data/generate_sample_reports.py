"""Generate sample PDF reports for mock data.

Uses raw PDF construction (no external libraries required).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_pdf(pages: list[list[str]]) -> bytes:
    """Build a minimal valid PDF from a list of pages, each page a list of text lines.

    Each line is rendered top-to-bottom with 14pt font, starting at y=750.
    Lines starting with '##' are rendered at 18pt, lines starting with '#' at 24pt.
    """
    objects: list[str] = []
    page_obj_ids: list[int] = []

    # Object 1: Catalog (placeholder, updated later)
    objects.append("")  # slot 0 unused (1-indexed)
    objects.append("")  # obj 1 = catalog
    objects.append("")  # obj 2 = pages

    # Font object
    font_obj_id = 3
    objects.append(f"{font_obj_id} 0 obj\n<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>\nendobj")
    font_bold_obj_id = 4
    objects.append(
        f"{font_bold_obj_id} 0 obj\n<</Type/Font/Subtype/Type1/BaseFont/Helvetica-Bold>>\nendobj"
    )

    next_id = 5

    for page_lines in pages:
        # Build content stream
        stream_parts: list[str] = []
        y = 750
        for line in page_lines:
            if line.startswith("## "):
                text = line[3:]
                stream_parts.append(f"BT /F2 18 Tf 50 {y} Td ({_pdf_escape(text)}) Tj ET")
                y -= 26
            elif line.startswith("# "):
                text = line[2:]
                stream_parts.append(f"BT /F2 24 Tf 50 {y} Td ({_pdf_escape(text)}) Tj ET")
                y -= 32
            elif line == "---":
                # Horizontal rule
                stream_parts.append(f"0.7 0.7 0.7 RG 0.5 w 50 {y + 8} m 562 {y + 8} l S")
                y -= 12
            elif line == "":
                y -= 10
            else:
                stream_parts.append(f"BT /F1 10 Tf 50 {y} Td ({_pdf_escape(line)}) Tj ET")
                y -= 16

        stream_content = "\n".join(stream_parts)
        stream_len = len(stream_content)

        content_obj_id = next_id
        next_id += 1
        objects.append(
            f"{content_obj_id} 0 obj\n"
            + f"<</Length {stream_len}>>\n"
            + f"stream\n{stream_content}\nendstream\n"
            + "endobj"
        )

        page_obj_id = next_id
        next_id += 1
        objects.append(
            f"{page_obj_id} 0 obj\n"
            + "<</Type/Page/Parent 2 0 R"
            + "/MediaBox[0 0 612 792]"
            + f"/Contents {content_obj_id} 0 R"
            + f"/Resources<</Font<</F1 {font_obj_id} 0 R/F2 {font_bold_obj_id} 0 R>>>>>>\n"
            + "endobj"
        )
        page_obj_ids.append(page_obj_id)

    # Now fill in catalog and pages
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects[1] = "1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj"
    objects[2] = f"2 0 obj\n<</Type/Pages/Kids[{kids}]/Count {len(page_obj_ids)}>>\nendobj"

    # Assemble PDF
    parts: list[str] = ["%PDF-1.4\n"]
    offsets: list[int] = [0]  # slot 0
    for i in range(1, len(objects)):
        offsets.append(len("".join(parts).encode("latin-1")))
        parts.append(objects[i] + "\n")

    xref_offset = len("".join(parts).encode("latin-1"))
    num_objects = len(objects)
    parts.append(f"xref\n0 {num_objects}\n")
    parts.append("0000000000 65535 f \n")
    for i in range(1, num_objects):
        parts.append(f"{offsets[i]:010d} 00000 n \n")
    parts.append(f"trailer\n<</Size {num_objects}/Root 1 0 R>>\nstartxref\n{xref_offset}\n%%EOF\n")

    return "".join(parts).encode("latin-1")


def _pdf_escape(text: str) -> str:
    """Escape special PDF string characters."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def generate_executive_report() -> bytes:
    """Generate the Executive Summary PDF."""
    page1 = [
        "# Executive Summary - March 2026",
        "",
        "---",
        "",
        "## Assets Under Management",
        "",
        "  Fund                          AUM (USD)",
        "  -------------------------------------------",
        "  Odum                          $18,000,000",
        "  Alpha Capital                 $15,000,000",
        "  Beta Fund                      $5,000,000",
        "  Vertex Partners               $15,000,000",
        "  -------------------------------------------",
        "  Total                         $53,000,000",
        "",
        "",
        "## Top Strategies by Return",
        "",
        "  Strategy                 MTD Return    Sharpe",
        "  ------------------------------------------------",
        "  Momentum Alpha           +3.12%        2.41",
        "  Mean Reversion Beta      +2.87%        1.98",
        "  Stat Arb Gamma           +2.45%        2.15",
        "  Volatility Delta         +1.93%        1.72",
        "  Trend Epsilon            +1.68%        1.54",
    ]

    page2 = [
        "# Risk Summary",
        "",
        "---",
        "",
        "## Portfolio Risk Metrics",
        "",
        "  Metric                        Value",
        "  ------------------------------------------",
        "  Portfolio VaR (95%)            $412,000",
        "  Portfolio VaR (99%)            $687,000",
        "  Expected Shortfall (95%)       $523,000",
        "  Max Drawdown (MTD)             -1.23%",
        "  Gross Exposure                 $78,400,000",
        "  Net Exposure                   $12,300,000",
        "  Beta to SPX                    0.12",
        "",
        "",
        "## Concentration Limits",
        "",
        "  Limit                     Current    Threshold    Status",
        "  -----------------------------------------------------------",
        "  Single Name               4.2%       5.0%         OK",
        "  Sector                    18.1%      20.0%        OK",
        "  Country                   32.4%      35.0%        OK",
        "  Asset Class               41.0%      50.0%        OK",
        "",
        "",
        "  Report generated: 2026-03-22 | Unified Trading System",
    ]

    return _build_pdf([page1, page2])


def generate_pnl_attribution() -> bytes:
    """Generate the P&L Attribution Report PDF."""
    page1 = [
        "# P&L Attribution Report",
        "",
        "---",
        "",
        "## Strategy Attribution - Top 10",
        "",
        "  #   Strategy                  Daily PnL      MTD PnL       YTD PnL",
        "  -----------------------------------------------------------------------",
        "  1   Momentum Alpha            +$42,300       +$312,000     +$1,245,000",
        "  2   Mean Reversion Beta       +$38,100       +$287,000     +$1,102,000",
        "  3   Stat Arb Gamma            +$31,500       +$245,000     +$987,000",
        "  4   Volatility Delta          +$27,200       +$193,000     +$812,000",
        "  5   Trend Epsilon             +$22,800       +$168,000     +$723,000",
        "  6   Pairs Zeta                +$18,400       +$142,000     +$598,000",
        "  7   Carry Eta                 +$15,600       +$118,000     +$487,000",
        "  8   Macro Theta               +$12,100       +$94,000      +$412,000",
        "  9   Event Iota                +$8,700        +$72,000      +$298,000",
        "  10  Dispersion Kappa          +$5,200        +$48,000      +$187,000",
        "  -----------------------------------------------------------------------",
        "       Total                    +$221,900      +$1,679,000   +$6,851,000",
        "",
        "",
        "## Attribution by Asset Class",
        "",
        "  Asset Class           Daily PnL      Allocation",
        "  --------------------------------------------------",
        "  Equities              +$98,400       42.1%",
        "  Fixed Income          +$52,300       23.8%",
        "  FX                    +$38,700       17.2%",
        "  Commodities           +$22,100       11.4%",
        "  Crypto                +$10,400       5.5%",
    ]

    page2 = [
        "# P&L Attribution - Continued",
        "",
        "---",
        "",
        "## Attribution by Region",
        "",
        "  Region                Daily PnL      Allocation",
        "  --------------------------------------------------",
        "  North America         +$112,500      48.3%",
        "  Europe                +$58,200       26.1%",
        "  Asia Pacific          +$38,900       18.7%",
        "  Emerging Markets      +$12,300       6.9%",
        "",
        "",
        "## Factor Decomposition",
        "",
        "  Factor                Contribution   Exposure",
        "  --------------------------------------------------",
        "  Market Beta           +$45,200       0.12",
        "  Momentum              +$62,300       0.34",
        "  Value                 +$28,100       0.18",
        "  Size                  +$12,400       0.08",
        "  Volatility            +$18,900       -0.15",
        "  Residual Alpha        +$55,000       --",
        "",
        "",
        "  Report generated: 2026-03-22 | Unified Trading System",
    ]

    return _build_pdf([page1, page2])


def main() -> None:
    """Generate all sample PDF reports."""
    output_dir = Path(__file__).parent / "sample_reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    executive_path = output_dir / "executive_report.pdf"
    _ = executive_path.write_bytes(generate_executive_report())
    logger.info("Generated: %s (%d bytes)", executive_path, os.path.getsize(executive_path))

    pnl_path = output_dir / "pnl_attribution.pdf"
    _ = pnl_path.write_bytes(generate_pnl_attribution())
    logger.info("Generated: %s (%d bytes)", pnl_path, os.path.getsize(pnl_path))


if __name__ == "__main__":
    main()
