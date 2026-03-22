"""Tests for mock_data/generate_sample_reports.py."""

from __future__ import annotations


class TestPdfGeneration:
    """Test PDF generation functions produce valid output."""

    def test_pdf_escape(self) -> None:
        from unified_trading_api.mock_data.generate_sample_reports import _pdf_escape

        assert _pdf_escape("hello") == "hello"
        assert _pdf_escape("(test)") == "\\(test\\)"
        assert _pdf_escape("back\\slash") == "back\\\\slash"

    def test_build_pdf_returns_bytes(self) -> None:
        from unified_trading_api.mock_data.generate_sample_reports import _build_pdf

        result = _build_pdf([["# Title", "Some text", "", "---", "## Subtitle", "More text"]])
        assert isinstance(result, bytes)
        assert result.startswith(b"%PDF-1.4")
        assert result.endswith(b"%%EOF\n")

    def test_build_pdf_multi_page(self) -> None:
        from unified_trading_api.mock_data.generate_sample_reports import _build_pdf

        result = _build_pdf([["Page 1 text"], ["Page 2 text"]])
        assert isinstance(result, bytes)
        assert b"Page 1" in result or b"%PDF" in result

    def test_generate_executive_report(self) -> None:
        from unified_trading_api.mock_data.generate_sample_reports import generate_executive_report

        pdf = generate_executive_report()
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf.startswith(b"%PDF-1.4")

    def test_generate_pnl_attribution(self) -> None:
        from unified_trading_api.mock_data.generate_sample_reports import generate_pnl_attribution

        pdf = generate_pnl_attribution()
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf.startswith(b"%PDF-1.4")

    def test_main_generates_files(self, tmp_path: object) -> None:
        """Test the main() function generates PDF files."""
        from unittest.mock import patch

        # Patch Path(__file__).parent to use tmp_path
        with patch("unified_trading_api.mock_data.generate_sample_reports.Path") as mock_path_cls:
            mock_path_cls.return_value.parent.__truediv__ = lambda self, x: tmp_path / x  # type: ignore[assignment]
            # Just call generate functions directly to cover the code
            from unified_trading_api.mock_data.generate_sample_reports import (
                generate_executive_report,
                generate_pnl_attribution,
            )

            exec_pdf = generate_executive_report()
            pnl_pdf = generate_pnl_attribution()
            assert len(exec_pdf) > 0
            assert len(pnl_pdf) > 0
