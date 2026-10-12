"""Paper metadata from Crossref, with citation-line fallbacks, and paper folder naming."""

import re
from dataclasses import dataclass

import requests

from paper_downloader import strategies
from paper_downloader.parsing import Line
from paper_downloader.strategies import quote_doi


@dataclass
class PaperMetadata:
    """A paper's year, first author's family name and journal. None means unknown."""

    year: str | None = None
    first_author: str | None = None
    journal: str | None = None


def fetch_crossref(doi: str, session: requests.Session, email: str) -> PaperMetadata:
    """Look up `doi` in Crossref. Any field Crossref lacks, or every field if the lookup fails, is None."""
    url = f"https://api.crossref.org/works/{quote_doi(doi)}"
    try:
        r = session.get(url, params={"mailto": email}, headers=strategies.HEADERS, timeout=15)
        if strategies._debug:
            print(f"  [crossref] {url} → status={r.status_code}")
        if r.status_code != 200:
            return PaperMetadata()
        message = r.json().get("message") or {}
    except Exception as e:
        if strategies._debug:
            print(f"  [crossref] exception: {e}")
        return PaperMetadata()

    meta = PaperMetadata()
    date_parts = (message.get("issued") or {}).get("date-parts") or [[]]
    if date_parts[0] and date_parts[0][0]:
        meta.year = str(date_parts[0][0])
    authors = message.get("author") or []
    if authors:
        # A consortium author has a `name` instead of a `family` name.
        meta.first_author = authors[0].get("family") or authors[0].get("name") or None
    titles = message.get("container-title") or []
    if titles:
        meta.journal = titles[0] or None
    if strategies._debug:
        print(f"  [crossref] resolved {meta}")
    return meta


def resolve_metadata(crossref: PaperMetadata, line: Line) -> PaperMetadata:
    """Take each field from Crossref, else from the citation line, else `0000` / `Unknown`."""
    return PaperMetadata(
        year=crossref.year or line.year or "0000",
        first_author=crossref.first_author or line.first_author or "Unknown",
        journal=crossref.journal or line.journal or "Unknown",
    )


def make_folder_name(meta: PaperMetadata) -> str:
    """`{year}_{FirstAuthor}_{Journal}`, with the journal reduced to alphanumerics."""
    author = re.sub(r"[^\w'\-]", "", meta.first_author or "Unknown")
    journal_slug = re.sub(r"[^a-zA-Z0-9]", "", meta.journal or "Unknown")
    return f"{meta.year or '0000'}_{author}_{journal_slug}"


def unique_name(base: str, used: set[str]) -> str:
    """Return `base`, or `base_2`, `base_3`, … if taken, and mark the result as used."""
    name, n = base, 1
    while name in used:
        n += 1
        name = f"{base}_{n}"
    used.add(name)
    return name
