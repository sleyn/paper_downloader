#!/usr/bin/env python3
"""Download PDFs for papers listed in List_of_papers.txt."""

import argparse
import re
import sys
import time
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from dotenv import dotenv_values
except ImportError:
    sys.exit("Missing dependency: pip install dotenv")

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing dependency: pip install beautifulsoup4")

config = dotenv_values(Path(__file__).resolve().parent /".env")
EMAIL = config.get("EMAIL", "").strip()
print(f"Using email: '{EMAIL}' (set EMAIL in .env or use --email to override)")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PaperDownloader/1.0; "
        f"mailto:{EMAIL})"
    )
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

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


def make_folder_name(year: str, author: str, journal: str) -> str:
    journal_slug = re.sub(r"[^a-zA-Z0-9]", "", journal)
    return f"{year}_{author}_{journal_slug}"


def unique_name(base: str, seen: dict) -> str:
    """Return a unique name by appending _2, _3, … if base already used."""
    if base not in seen:
        seen[base] = 1
        return base
    seen[base] += 1
    return f"{base}_{seen[base]}"


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_url(url: str, session: requests.Session, timeout: int = 30) -> bytes | None:
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 1024:
            ct = r.headers.get("Content-Type", "")
            if "pdf" in ct or r.content[:4] == b"%PDF":
                return r.content
    except Exception:
        pass
    return None


def try_unpaywall(doi: str, session: requests.Session) -> bytes | None:
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}"
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        if pdf_url:
            result = download_url(pdf_url, session)
            if result:
                return result
        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf") or loc.get("url")
            if pdf_url:
                result = download_url(pdf_url, session)
                if result:
                    return result
    except Exception:
        pass
    return None


def try_europe_pmc(doi: str, session: requests.Session) -> bytes | None:
    try:
        search_url = (
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            f"?query=DOI:{doi}&format=json&resultType=core"
        )
        r = session.get(search_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        results = r.json().get("resultList", {}).get("result", [])
        for item in results:
            full_text_url_list = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
            for full_text_url in full_text_url_list:
                if full_text_url.get("documentStyle") == "pdf":
                    result = download_url(full_text_url.get("url"), session)
                    if result:
                        return result
    except Exception:
        pass
    return None


def try_pubmed_central(doi: str, session: requests.Session, email: str) -> bytes | None:
    try:
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pmc&term={doi}[doi]&retmode=json&email={email}&tool=paper_downloader"
        )
        r = session.get(search_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return None
        time.sleep(0.35)
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{ids[0]}/pdf/"
        return download_url(pdf_url, session)
    except Exception:
        pass
    return None


def try_semantic_scholar(doi: str, session: requests.Session) -> bytes | None:
    try:
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            f"?fields=openAccessPdf"
        )
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        oa = r.json().get("openAccessPdf") or {}
        pdf_url = oa.get("url")
        if pdf_url:
            return download_url(pdf_url, session)
    except Exception:
        pass
    return None


def try_direct_doi(doi_url: str, session: requests.Session) -> tuple[bytes | None, str | None]:
    """Return (pdf_bytes_or_None, landing_page_html_or_None)."""
    try:
        r = session.get(doi_url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None, None
        ct = r.headers.get("Content-Type", "")
        if "pdf" in ct or r.content[:4] == b"%PDF":
            return r.content, None
        if "html" in ct:
            return None, r.text
    except Exception:
        pass
    return None, None


def fetch_landing_html(doi_url: str, session: requests.Session) -> str | None:
    try:
        r = session.get(doi_url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("Content-Type", ""):
            return r.text
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------

def process_paper(
    paper: dict,
    folder: Path,
    base_name: str,
    session: requests.Session,
    delay: float,
) -> str | None:
    """
    Try all strategies to download the PDF files.
    Returns None on success, or an error string on failure.
    """
    doi = paper["doi"]
    doi_url = paper["doi_url"]
    pdf_path = folder / f"{base_name}.pdf"

    print(f"  Trying Unpaywall ...", end=" ", flush=True)
    pdf_bytes = try_unpaywall(doi, session)
    time.sleep(delay)

    if not pdf_bytes:
        print("miss. Trying Europe PMC ...", end=" ", flush=True)
        pdf_bytes = try_europe_pmc(doi, session)
        time.sleep(delay)

    if not pdf_bytes:
        print("miss. Trying PubMed Central ...", end=" ", flush=True)
        pdf_bytes = try_pubmed_central(doi, session, EMAIL)
        time.sleep(delay)

    if not pdf_bytes:
        print("miss. Trying Semantic Scholar ...", end=" ", flush=True)
        pdf_bytes = try_semantic_scholar(doi, session)
        time.sleep(delay)

    if not pdf_bytes:
        print("miss. Trying direct DOI ...", end=" ", flush=True)
        pdf_bytes, _ = try_direct_doi(doi_url, session)
        time.sleep(delay)

    if pdf_bytes:
        folder.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(pdf_bytes)
        print(f"saved ({len(pdf_bytes) // 1024} KB)")
    else:
        print("not found.")

    if not pdf_bytes:
        return "PDF not found via any strategy"
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global EMAIL

    parser = argparse.ArgumentParser(
        description="Download PDFs and supplementary for papers in List_of_papers.txt"
    )
    parser.add_argument(
        "--input",
        default="reference/List_of_papers.txt",
        help="Path to the papers list file",
    )
    parser.add_argument(
        "--output",
        default="reference/papers",
        help="Root directory for downloaded papers",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between HTTP requests (default: 1.0)",
    )
    parser.add_argument(
        "--email",
        type=str,
        default="-",
        help="Email address for API requests (default: use EMAIL environment variable)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    failed_log = output_dir / "failed_downloads.txt"

    if EMAIL is None:
        if args.email != "-":
            EMAIL = args.email
        else:
            sys.exit("Email address is required. Set it in the .env file or use --email to provide it.")

    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    lines = [l for l in input_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    papers = []
    for line in lines:
        parsed = parse_line(line)
        if parsed:
            papers.append(parsed)

    print(f"Parsed {len(papers)} papers from {input_path}")
    print(f"Output directory: {output_dir}\n")

    seen_names: dict[str, int] = {}
    failures: list[str] = []

    session = requests.Session()

    for i, paper in enumerate(papers, start=1):
        base = make_folder_name(paper["year"], paper["first_author"], paper["journal"])
        name = unique_name(base, seen_names)
        folder = output_dir / name

        print(f"[{i}/{len(papers)}] {name}")
        print(f"  DOI: {paper['doi_url']}")

        error = process_paper(paper, folder, name, session, args.delay)
        if error:
            failures.append(f"{paper['doi_url']}  # {error}  | {paper['raw']}")
        print()

    if failures:
        failed_log.write_text("\n".join(failures) + "\n", encoding="utf-8")
        print(f"\n{len(failures)} paper(s) could not be downloaded.")
        print(f"See: {failed_log}")
    else:
        print("\nAll papers downloaded successfully.")


if __name__ == "__main__":
    main()
