"""Extract a paper's DOI and paper metadata from a citation line."""

import re


def parse_line(raw: str) -> dict | None:
    """Return parsed paper dict or None if the line is unparseable."""
    line = raw.strip()
    line = re.sub(r"^\d+\.\s*", "", line)
    if not line:
        return None

    doi_match = re.search(r"https://doi\.org/(\S+?)\.?\s*$", line)
    if not doi_match:
        return None
    doi_url = doi_match.group(0).rstrip(".")
    doi = doi_match.group(1).rstrip(".")

    before_doi = line[: doi_match.start()]
    year_match = re.search(r"\b((?:19|20)\d{2})\b", before_doi)
    year = year_match.group(1) if year_match else "0000"

    first_author_match = re.match(r"([A-Za-z][A-Za-z'\-]+)", line)
    first_author = first_author_match.group(1) if first_author_match else "Unknown"

    journal = "Unknown"
    if year_match:
        chunk = before_doi[: year_match.start()].rstrip(", ")
        last_period = chunk.rfind(". ")
        if last_period != -1:
            journal = chunk[last_period + 2 :].strip().rstrip(",").strip()
        else:
            journal = chunk.strip().rstrip(",").strip()
        journal = re.sub(r",\s*Abstract\s*$", "", journal, flags=re.IGNORECASE).strip()

    return {
        "doi": doi,
        "doi_url": doi_url,
        "year": year,
        "first_author": first_author,
        "journal": journal,
        "raw": raw.strip(),
    }
