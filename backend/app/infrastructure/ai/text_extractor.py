"""Text extraction adapter supporting plain text, JSON, and PDF files."""

from io import BytesIO

from pypdf import PdfReader


class DefaultTextExtractor:
    """TextExtractorPort implementation for common document formats."""

    def extract_text(self, content: bytes, mime_type: str) -> str:
        """Extract UTF-8 text from PDF or text-like payloads."""
        if not content:
            return ""

        normalized_mime = mime_type.lower().split(";")[0].strip()
        if normalized_mime == "application/pdf":
            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()

        if normalized_mime.startswith("text/") or normalized_mime in {
            "application/json",
            "application/xml",
            "application/csv",
        }:
            return content.decode("utf-8", errors="replace").strip()

        return content.decode("utf-8", errors="ignore").strip()
