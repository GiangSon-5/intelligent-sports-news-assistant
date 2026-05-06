"""
Reporting Module — pdf_exporter.py
Markdown → HTML → PDF via fpdf2 according to SPEC §3.3.
Uses fpdf2's HTML rendering for accurate table and format support.
"""

import time
import os
from pathlib import Path
from typing import Optional
import markdown as md_lib

from logger import get_logger, log_function

_log = get_logger("reporting.pdf")


class PdfExporter:
    """
    Convert Markdown → HTML → PDF via fpdf2.
    Supports tables, bold text, and Vietnamese Unicode fonts.
    """

    def __init__(self):
        self._fpdf_available = False
        self._check_fpdf()

    def _find_vietnamese_font(self, style: str = "") -> Optional[str]:
        """Look for font files for different styles (Regular, Bold, Italic, Bold-Italic)."""
        font_map = {
            "": "arial.ttf",
            "B": "arialbd.ttf",
            "I": "ariali.ttf",
            "BI": "arialbi.ttf",
        }
        
        filename = font_map.get(style, "arial.ttf")
        path = os.path.join("C:\\Windows\\Fonts", filename)
        
        if os.path.exists(path):
            return path
        
        # Fallback for Linux or if Arial is missing
        fallbacks = ["tahoma.ttf", "DejaVuSans.ttf"]
        for fb in fallbacks:
            fb_path = os.path.join("C:\\Windows\\Fonts", fb)
            if os.path.exists(fb_path):
                return fb_path
                
        return None

    def _check_fpdf(self) -> None:
        """Check if fpdf2 is available."""
        try:
            from fpdf import FPDF # noqa: F401
            self._fpdf_available = True
            _log.info("PdfExporter initialized | fpdf2 available ✓")
        except ImportError:
            self._fpdf_available = False
            _log.warning("fpdf2 not found. Run: pip install fpdf2")

    @property
    def is_available(self) -> bool:
        """Check if PDF export is available."""
        return self._fpdf_available

    @log_function("reporting.pdf")
    def export(self, markdown_content: str, output_path: str) -> str:
        """
        Convert Markdown → HTML → PDF.
        """
        start = time.perf_counter()

        if not self._fpdf_available:
            raise ImportError("fpdf2 is not installed. Run: pip install fpdf2")

        from fpdf import FPDF, HTMLMixin

        class HTMLPDF(FPDF, HTMLMixin):
            pass

        pdf = HTMLPDF()
        
        # Register all 4 styles to prevent fallback to Helvetica
        styles = ["", "B", "I", "BI"]
        for s in styles:
            fpath = self._find_vietnamese_font(s)
            if fpath:
                pdf.add_font("Arial", s, fpath)
            elif s != "": # If bold/italic missing, use regular
                pdf.add_font("Arial", s, self._find_vietnamese_font(""))

        pdf.add_page()
        pdf.set_font("Arial", size=11)

        # Step 1: Convert Markdown to HTML
        html_content = md_lib.markdown(
            markdown_content, 
            extensions=['tables', 'fenced_code', 'nl2br']
        )

        # Step 2: Clean up HTML
        # Ensure we use Arial in the HTML tags
        html_content = f'<font face="Arial">{html_content}</font>'

        # Step 3: Write HTML to PDF
        try:
            pdf.write_html(html_content)
        except Exception as e:
            _log.warning(f"HTML rendering warning: {e}")
            pdf.ln(5)
            pdf.write(5, "Error rendering some HTML elements. Content might be incomplete.")

        # Ensure output dir exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf.output(output_path)

        file_size = Path(output_path).stat().st_size
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        _log.info(
            f"PDF exported (HTML mode) | path={output_path} | "
            f"size={file_size} bytes | latency={elapsed}ms"
        )

        return output_path
