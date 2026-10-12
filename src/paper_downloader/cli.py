"""Command-line entry point: argument handling, email resolution and the per-paper waterfall."""

import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import dotenv_values

from paper_downloader import strategies
from paper_downloader.metadata import fetch_crossref, make_folder_name, resolve_metadata, unique_name
from paper_downloader.parsing import (
    BLANK,
    CITATION_LINE,
    COMMENT,
    DOI_LINE,
    SKIPPED_LINE,
    Line,
    parse_line,
)
from paper_downloader.strategies import (
    try_direct_doi,
    try_europe_pmc,
    try_semantic_scholar,
    try_unpaywall,
)

# Strategies in the order they are tried. See docs/adr/0001-drop-pubmed-central-strategy.md.
WATERFALL = [
    ("Unpaywall", try_unpaywall),
    ("Europe PMC", try_europe_pmc),
    ("Semantic Scholar", try_semantic_scholar),
    ("direct DOI", try_direct_doi),
]


# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------

def process_paper(
    paper: Line,
    folder: Path,
    base_name: str,
    session: requests.Session,
    delay: float,
) -> str | None:
    """
    Try each strategy in turn until one returns the PDF.
    Returns None on success, or an error string on failure.
    """
    pdf_path = folder / f"{base_name}.pdf"
    pdf_bytes = None

    for i, (label, strategy) in enumerate(WATERFALL):
        print(f"{'miss. ' if i else '  '}Trying {label} ...", end=" ", flush=True)
        pdf_bytes = strategy(paper.doi, session)
        time.sleep(delay)
        if pdf_bytes:
            break

    if not pdf_bytes:
        print("not found.")
        return "PDF not found via any strategy"

    folder.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)
    print(f"saved ({len(pdf_bytes) // 1024} KB)")
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def write_failure_log(path: Path, failures: list[tuple[Line, str]]) -> None:
    """Write each failure as a `# reason` comment followed by its original line, so the file is a paper list."""
    entries = sorted(failures, key=lambda failure: failure[0].number)
    path.write_text("".join(f"# {reason}\n{line.raw}\n" for line, reason in entries), encoding="utf-8")


def count_kinds(lines: list[Line]) -> str:
    """Summarise how many lines of each kind the paper list holds, e.g. "2 DOI lines, 1 comment"."""
    parts = []
    for kind in (CITATION_LINE, DOI_LINE, SKIPPED_LINE, COMMENT, BLANK):
        n = sum(1 for line in lines if line.kind == kind)
        noun = kind if kind != BLANK else "blank line"
        parts.append(f"{n} {noun}{'' if n == 1 else 's'}")
    return ", ".join(parts)


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

    lines = [
        parse_line(raw, number)
        for number, raw in enumerate(input_path.read_text(encoding="utf-8").splitlines(), start=1)
    ]
    papers = [line for line in lines if line.kind in (CITATION_LINE, DOI_LINE)]
    skipped = [line for line in lines if line.kind == SKIPPED_LINE]

    print(f"Read {input_path}: {count_kinds(lines)}")
    if skipped:
        print(f"\nWarning: {len(skipped)} line(s) with no DOI found were skipped:")
        for line in skipped:
            print(f"  line {line.number}: {line.raw.strip()[:80]}")
    print(f"\nOutput directory: {output_dir}\n")

    seen_names: dict[str, int] = {}
    # (line, reason) for every line that goes in the failure log.
    failures: list[tuple[Line, str]] = [(line, f"no DOI found (line {line.number})") for line in skipped]

    session = requests.Session()

    for i, paper in enumerate(papers, start=1):
        print(f"[{i}/{len(papers)}] DOI: {paper.doi_url}")
        crossref = fetch_crossref(paper.doi, session, strategies.EMAIL)
        time.sleep(args.delay)
        base = make_folder_name(resolve_metadata(crossref, paper))
        name = unique_name(base, seen_names)
        folder = output_dir / name
        print(f"  Paper folder: {name}")

        error = process_paper(paper, folder, name, session, args.delay)
        if error:
            failures.append((paper, error))
        print()

    if failures:
        write_failure_log(failed_log, failures)
        print(f"\n{len(failures)} line(s) need attention.")
        print(f"See: {failed_log}")
    else:
        failed_log.unlink(missing_ok=True)
        print("\nAll papers downloaded successfully.")


if __name__ == "__main__":
    main()
