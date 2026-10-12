"""Canned API replies for tests."""

import re
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


def crossref_url(doi: str) -> str:
    return f"https://api.crossref.org/works/{quote(doi, safe='/')}"


def crossref_record(http, doi: str, *, year=None, family=None, name=None, journal=None) -> None:
    """Crossref knows `doi`. Fields left as None are absent from the record."""
    message: dict = {}
    if year is not None:
        message["issued"] = {"date-parts": [[year, 3, 14]]}
    if family is not None or name is not None:
        author = {"family": family} if family is not None else {"name": name}
        message["author"] = [author, {"given": "Second", "family": "Author"}]
    if journal is not None:
        message["container-title"] = [journal, "Short title"]
    http.get(crossref_url(doi), json={"status": "ok", "message": message})


def crossref_missing(http, doi: str, status: int = 404) -> None:
    """Crossref has no record of `doi` (404) or is down (5xx)."""
    http.get(crossref_url(doi), status=status)


def miss_everywhere(http) -> None:
    """Every strategy misses every DOI."""
    for pattern in (
        r"https://api\.unpaywall\.org/.*",
        r"https://www\.ebi\.ac\.uk/.*",
        r"https://api\.semanticscholar\.org/.*",
        r"https://doi\.org/.*",
    ):
        http.get(re.compile(pattern), status=404)
