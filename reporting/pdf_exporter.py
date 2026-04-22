"""
Reporting Module — pdf_exporter.py
Markdown → HTML → PDF via WeasyPrint according to SPEC §3.3.
WeasyPrint is an OPTIONAL dependency (Edge Case #6).
"""

import time
from pathlib import Path

from logger import get_logger, log_function

_log = get_logger("reporting.pdf")


# CSS Styling for PDF (SPEC §3.3 / SRS Rule #9)
_PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap');

body {
    font-family: 'Noto Sans', 'Segoe UI', 'Arial', sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px;
    color: #333;
    line-height: 1.7;
    font-size: 14px;
}

h1 {
    color: #1a73e8;
    border-bottom: 3px solid #1a73e8;
    padding-bottom: 12px;
    font-size: 24px;
    margin-top: 0;
}

h2 {
    color: #34a853;
    margin-top: 35px;
    font-size: 20px;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 8px;
}

h3 {
    color: #4285f4;
    font-size: 16px;
    margin-top: 25px;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 20px 0;
    font-size: 13px;
}

th, td {
    border: 1px solid #ddd;
    padding: 10px 12px;
    text-align: left;
}

th {
    background: #f1f3f4;
    font-weight: 600;
    color: #333;
}

tr:nth-child(even) {
    background: #fafafa;
}

blockquote {
    border-left: 4px solid #4285f4;
    margin: 15px 0;
    padding: 12px 20px;
    background: #f8f9fa;
    border-radius: 0 4px 4px 0;
    font-style: normal;
}

blockquote p {
    margin: 5px 0;
}

a {
    color: #1a73e8;
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 30px 0;
}

p:last-child {
    color: #888;
    font-size: 12px;
    font-style: italic;
}

strong {
    font-weight: 600;
}

@page {
    size: A4;
    margin: 2cm;
}
"""


class PdfExporter:
    """
    Convert Markdown → HTML → PDF via WeasyPrint.
    WeasyPrint is an optional dependency — if not installed, skip gracefully.
    """

    def __init__(self):
        self._weasyprint_available = False
        self._check_weasyprint()

    def _check_weasyprint(self) -> None:
        """Check if WeasyPrint is available. Batched to handle GTK issues on Windows."""
        try:
            import weasyprint  # noqa: F401
            self._weasyprint_available = True
            _log.info("PdfExporter initialized | WeasyPrint available ✓")
        except (ImportError, OSError) as e:
            self._weasyprint_available = False
            _log.warning(f"WeasyPrint check failed: {e}. PDF export disabled.")

    @property
    def is_available(self) -> bool:
        """Check if PDF export is available."""
        return self._weasyprint_available

    @log_function("reporting.pdf")
    def export(self, markdown_content: str, output_path: str) -> str:
        """
        Convert Markdown → HTML → PDF.

        Args:
            markdown_content: Rendered Markdown string
            output_path: Path to output PDF file

        Returns:
            str: Path to the created PDF file

        Raises:
            ImportError: If WeasyPrint is not installed
            Exception: Other error when rendering PDF
        """
        start = time.perf_counter()

        if not self._weasyprint_available:
            raise ImportError(
                "WeasyPrint is not installed. "
                "Install: pip install WeasyPrint "
                "(requires system dependencies: GTK+, Pango)"
            )

        import markdown as md_lib
        from weasyprint import HTML

        # Step 1: Markdown → HTML
        html_body = md_lib.markdown(
            markdown_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )

        # Step 2: Wrap in full HTML document with CSS
        full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Sports Report</title>
    <style>{_PDF_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

        # Step 3: HTML → PDF
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        HTML(string=full_html).write_pdf(output_path)

        file_size = Path(output_path).stat().st_size
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        _log.info(
            f"PDF exported | path={output_path} | "
            f"size={file_size} bytes | latency={elapsed}ms"
        )

        return output_path
