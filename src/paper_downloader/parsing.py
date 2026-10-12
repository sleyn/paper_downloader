"""Classify paper list lines and extract each paper's DOI, plus fallback paper metadata from citation lines."""

import re
from dataclasses import dataclass

BLANK = "blank"
COMMENT = "comment"
DOI_LINE = "DOI line"
CITATION_LINE = "citation line"
SKIPPED_LINE = "skipped line"

_DOI = r"10\.\d{4,9}/\S+"
# The whole line is a DOI: https://doi.org/…, http://dx.doi.org/…, doi:… or a bare 10.…
_DOI_LINE_RE = re.compile(rf"(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?({_DOI})", re.IGNORECASE)
# A DOI URL somewhere inside citation text.
_CITATION_DOI_RE = re.compile(rf"https?://(?:dx\.)?doi\.org/({_DOI})", re.IGNORECASE)
# "12. " at the start of a numbered bibliography entry. The required space keeps a bare "10.1234/…" intact.
_NUMBERING_RE = re.compile(r"^\d+\.\s+")


@dataclass
class Line:
    """One line of a paper list. `doi` is non-empty only for DOI lines and citation lines."""

    number: int
    raw: str
    kind: str
    doi: str = ""
    # Fallback paper metadata parsed from a citation line; None when absent.
    year: str | None = None
    first_author: str | None = None
    journal: str | None = None

    @property
    def doi_url(self) -> str:
        return f"https://doi.org/{self.doi}"


def parse_line(raw: str, number: int) -> Line:
    """Classify one paper list line (1-based `number`) and extract what it holds."""
    text = raw.strip()
    if not text:
        return Line(number, raw, BLANK)
    if text.startswith("#"):
        return Line(number, raw, COMMENT)

    text = _NUMBERING_RE.sub("", text)

    doi_match = _DOI_LINE_RE.fullmatch(text)
    if doi_match:
        return Line(number, raw, DOI_LINE, doi=_clean_doi(doi_match.group(1)))

    doi_match = _CITATION_DOI_RE.search(text)
    if doi_match:
        line = Line(number, raw, CITATION_LINE, doi=_clean_doi(doi_match.group(1)))
        _parse_citation_metadata(text[: doi_match.start()], line)
        return line

    return Line(number, raw, SKIPPED_LINE)


def _clean_doi(doi: str) -> str:
    """Drop the trailing period of a DOI that ends a sentence."""
    return doi.rstrip(".")


def _parse_citation_metadata(before_doi: str, line: Line) -> None:
    """Fill year, first author and journal from the citation text before the DOI URL."""
    year_match = re.search(r"\b((?:19|20)\d{2})\b", before_doi)
    if year_match:
        line.year = year_match.group(1)

    first_author_match = re.match(r"([A-Za-z][A-Za-z'\-]+)", before_doi)
    if first_author_match:
        line.first_author = first_author_match.group(1)

    if year_match:
        chunk = before_doi[: year_match.start()].rstrip(", ")
        last_period = chunk.rfind(". ")
        if last_period != -1:
            journal = chunk[last_period + 2 :].strip().rstrip(",").strip()
        else:
            journal = chunk.strip().rstrip(",").strip()
        journal = re.sub(r",\s*Abstract\s*$", "", journal, flags=re.IGNORECASE).strip()
        line.journal = journal or None
