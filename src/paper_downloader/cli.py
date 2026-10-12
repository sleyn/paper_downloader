"""Command-line entry point: argument handling, email resolution and the per-paper waterfall."""

import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

from paper_downloader import strategies
from paper_downloader.metadata import make_folder_name, unique_name
from paper_downloader.parsing import parse_line
from paper_downloader.strategies import (
    try_direct_doi,
    try_europe_pmc,
    try_pubmed_central,
    try_semantic_scholar,
    try_unpaywall,
)


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
        pdf_bytes = try_pubmed_central(doi, session, strategies.EMAIL)
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

def resolve_email(flag: str | None) -> str:
    """Return the email from --email, else the EMAIL environment variable, else .env in the current directory."""
    for candidate in (
        flag,
        os.environ.get("EMAIL"),
        dotenv_values(Path.cwd() / ".env").get("EMAIL"),
    ):
        if candidate and candidate.strip():
            return candidate.strip()
    return ""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Download open-access PDFs for papers in a paper list."
    )
    parser.add_argument(
        "--input",
        default="List_of_papers.txt",
        help="Path to the paper list (default: List_of_papers.txt)",
    )
    parser.add_argument(
        "--output",
        default="papers",
        help="Root directory for downloaded papers (default: papers)",
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
        default=None,
        help="Email address for API requests (default: EMAIL environment variable, then EMAIL in ./.env)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print verbose debug output for each HTTP request",
    )
    args = parser.parse_args(argv)

    strategies._debug = args.debug

    input_path = Path(args.input)
    output_dir = Path(args.output)
    failed_log = output_dir / "failed_downloads.txt"

    strategies.EMAIL = resolve_email(args.email)
    if not strategies.EMAIL:
        sys.exit(
            "Email address is required. Use --email, set the EMAIL environment variable, "
            "or put EMAIL=... in a .env file in the current directory."
        )
    email = strategies.EMAIL
    strategies.HEADERS["User-Agent"] = f"Mozilla/5.0 (compatible; PaperDownloader/1.0; mailto:{email})"
    print(f"Using email: '{email}'")

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
