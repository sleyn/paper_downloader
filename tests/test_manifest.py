"""The manifest records downloads, so re-runs skip papers already present."""

import re

import pytest
from fakes import FAKE_PDF, crossref_missing, crossref_record, unpaywall_hit

DOI = "10.1038/s41467-024-12345-6"
FOLDER = "2024_Leyn_NatureCommunications"


def paper_available(http, doi: str = DOI, family: str = "Leyn") -> None:
    crossref_record(http, doi, year=2024, family=family, journal="Nature Communications")
    unpaywall_hit(http, doi)


def test_second_run_makes_no_requests_for_downloaded_papers(run, http):
    paper_available(http)
    run([DOI])
    first_run_calls = len(http.calls)

    out = run([DOI])

    assert len(http.calls) == first_run_calls
    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF


def manifest_rows(out) -> list[list[str]]:
    return [line.split("\t") for line in (out / "manifest.tsv").read_text().splitlines()]


def test_manifest_records_doi_folder_strategy_and_date(run, http):
    paper_available(http)

    out = run([DOI])

    header, row = manifest_rows(out)
    assert header == ["doi", "folder", "strategy", "date"]
    assert row[:3] == [DOI, FOLDER, "unpaywall"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row[3])


def test_deleted_pdf_is_downloaded_again(run, http):
    paper_available(http)
    out = run([DOI])
    (out / FOLDER / f"{FOLDER}.pdf").unlink()
    unpaywall_hit(http, DOI)

    run([DOI])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert len(manifest_rows(out)) == 2


def test_force_redownloads_and_replaces_the_manifest_row(run, http):
    paper_available(http)
    out = run([DOI])
    newer_pdf = FAKE_PDF + b"v2"
    unpaywall_hit(http, DOI, pdf=newer_pdf)

    run([DOI], "--force")

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == newer_pdf
    assert [row[0] for row in manifest_rows(out)] == ["doi", DOI]


def test_new_paper_colliding_with_earlier_run_folder_gets_suffix(run, http):
    paper_available(http)
    out = run([DOI])
    other = "10.1038/s41467-024-99999-9"
    paper_available(http, other)

    run([DOI, other])

    assert (out / f"{FOLDER}_2" / f"{FOLDER}_2.pdf").exists()
    assert [row[1] for row in manifest_rows(out)[1:]] == [FOLDER, f"{FOLDER}_2"]


def test_interrupted_run_keeps_rows_for_papers_already_saved(run, http, tmp_path):
    paper_available(http)
    later = "10.1038/s41467-024-99999-9"

    def interrupt(request):
        raise KeyboardInterrupt

    http.add_callback("GET", f"https://api.crossref.org/works/{later}", callback=interrupt)

    with pytest.raises(KeyboardInterrupt):
        run([DOI, later])

    assert [row[0] for row in manifest_rows(tmp_path / "out")] == ["doi", DOI]


def test_summary_counts_downloaded_present_and_failed(run, http, capsys):
    paper_available(http)
    run([DOI])
    new = "10.1038/s41467-024-99999-9"
    paper_available(http, new, family="Smith")
    missing = "10.1000/missing"
    crossref_missing(http, missing)
    for pattern in (r"https://api\.unpaywall\.org/.*", r"https://www\.ebi\.ac\.uk/.*",
                    r"https://api\.semanticscholar\.org/.*", r"https://doi\.org/.*"):
        http.get(re.compile(pattern), status=404)
    capsys.readouterr()

    out = run([DOI, new, missing])

    console = capsys.readouterr().out
    assert "1 downloaded, 1 already present, 1 failed" in console
    assert str(out / "failed_downloads.txt") in console
