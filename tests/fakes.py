"""Canned API replies for tests."""

from urllib.parse import quote

# Large enough to pass the downloader's "more than 1 KB" check.
FAKE_PDF = b"%PDF-1.4\n" + b"0" * 2048


def unpaywall_hit(http, doi: str, pdf: bytes = FAKE_PDF) -> None:
    """Unpaywall finds `doi`, and its PDF URL returns `pdf`."""
    pdf_url = f"https://oa.example.org/{quote(doi, safe='')}.pdf"
    http.get(
        f"https://api.unpaywall.org/v2/{quote(doi, safe='/')}",
        json={"best_oa_location": {"url_for_pdf": pdf_url}},
    )
    http.get(pdf_url, body=pdf, content_type="application/pdf")
