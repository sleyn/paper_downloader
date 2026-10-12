"""Command-line entry point: arguments, email resolution, the manifest, the failure log and the per-paper waterfall."""

import argparse
import csv
import os
import sys
import time
from datetime import date
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

# Strategies in the order they are tried: (console label, name recorded in the manifest, function).
# See docs/adr/0001-drop-pubmed-central-strategy.md.
WATERFALL = [
    ("Unpaywall", "unpaywall", try_unpaywall),
    ("Europe PMC", "europe_pmc", try_europe_pmc),
    ("Semantic Scholar", "semantic_scholar", try_semantic_scholar),
    ("direct DOI", "direct_doi", try_direct_doi),
]

MANIFEST_NAME = "manifest.tsv"
MANIFEST_COLUMNS = ["doi", "folder", "strategy", "date"]
FAILURE_LOG_NAME = "failed_downloads.txt"


# ---------------------------------------------------------------------------
# Main download logic
# ---------------------------------------------------------------------------

def process_paper(paper: Line, folder: Path, session: requests.Session, delay: float) -> str | None:
    """
    Try each strategy in turn until one returns the PDF, and save it as `<folder>/<folder name>.pdf`.
    Returns the manifest name of the strategy that succeeded, or None if every strategy missed.
    """
    for i, (label, name, strategy) in enumerate(WATERFALL):
        print(f"{'miss. ' if i else '  '}Trying {label} ...", end=" ", flush=True)
        pdf_bytes = strategy(paper.doi, session)
        time.sleep(delay)
        if pdf_bytes:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{folder.name}.pdf").write_bytes(pdf_bytes)
            print(f"saved ({len(pdf_bytes) // 1024} KB)")
            return name

    print("not found.")
    return None


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def read_manifest(path: Path) -> dict[str, dict[str, str]]:
    """Return the manifest rows keyed by DOI, in file order. A missing manifest is empty."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {row["doi"]: row for row in csv.DictReader(f, delimiter="\t")}


def record_download(path: Path, manifest: dict[str, dict[str, str]], row: dict[str, str]) -> None:
    """Add `row` to the manifest on disk right away. A DOI already listed has its row replaced."""
    replacing = row["doi"] in manifest
    manifest[row["doi"]] = row
    if replacing or not path.exists():
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, MANIFEST_COLUMNS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(manifest.values())
    else:
        with path.open("a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, MANIFEST_COLUMNS, delimiter="\t", lineterminator="\n").writerow(row)


# ---------------------------------------------------------------------------
# Output
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
        "--force",
        action="store_true",
        help="Download every paper again, even if the manifest says its PDF is already present",
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
    failed_log = output_dir / FAILURE_LOG_NAME
    manifest_path = output_dir / MANIFEST_NAME

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
        print(f"\nWarning: {len(skipped)} skipped line(s), no DOI found:")
        for line in skipped:
            print(f"  line {line.number}: {line.raw.strip()[:80]}")
    print(f"\nOutput directory: {output_dir}\n")

    manifest = read_manifest(manifest_path)
    # Seeded from earlier runs so a new paper never takes an existing paper folder's name.
    used_names = {row["folder"] for row in manifest.values()}
    # (line, reason) for every line that goes in the failure log.
    failures: list[tuple[Line, str]] = [(line, f"no DOI found (line {line.number})") for line in skipped]
    downloaded = already_present = 0

    session = requests.Session()

    for i, paper in enumerate(papers, start=1):
        print(f"[{i}/{len(papers)}] DOI: {paper.doi_url}")
        listed = manifest.get(paper.doi)
        if listed:
            name = listed["folder"]
            if not args.force and (output_dir / name / f"{name}.pdf").exists():
                print(f"  Already present: {name}\n")
                already_present += 1
                continue
        else:
            crossref = fetch_crossref(paper.doi, session, email)
            time.sleep(args.delay)
            name = unique_name(make_folder_name(resolve_metadata(crossref, paper)), used_names)
        print(f"  Paper folder: {name}")

        strategy = process_paper(paper, output_dir / name, session, args.delay)
        if strategy:
            row = {"doi": paper.doi, "folder": name, "strategy": strategy, "date": date.today().isoformat()}
            record_download(manifest_path, manifest, row)
            downloaded += 1
        else:
            failures.append((paper, "PDF not found via any strategy"))
        print()

    failed = len(failures) - len(skipped)
    print(f"\nDone: {downloaded} downloaded, {already_present} already present, {failed} failed.")
    if failures:
        write_failure_log(failed_log, failures)
        print(f"Failure log ({len(failures)} entries): {failed_log}")
    else:
        failed_log.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
