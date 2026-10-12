"""End-to-end downloads through the CLI."""

from fakes import FAKE_PDF, crossref_missing, unpaywall_hit

from paper_downloader import cli

CITATION = (
    "1. Leyn SA, Kazanov MD, Suvorova IA. A study of things. Nature Communications. 2024. "
    "https://doi.org/10.1038/s41467-024-12345-6"
)
DOI = "10.1038/s41467-024-12345-6"


def test_citation_line_saved_from_unpaywall(run, http):
    crossref_missing(http, DOI)
    unpaywall_hit(http, DOI)

    out = run([CITATION])

    pdf = out / "2024_Leyn_NatureCommunications" / "2024_Leyn_NatureCommunications.pdf"
    assert pdf.read_bytes() == FAKE_PDF
    assert not (out / "failed_downloads.txt").exists()


def test_defaults_read_list_and_write_papers_in_current_directory(tmp_path, http):
    crossref_missing(http, DOI)
    unpaywall_hit(http, DOI)
    (tmp_path / "List_of_papers.txt").write_text(CITATION + "\n", encoding="utf-8")

    cli.main(["--delay", "0", "--email", "test@example.com"])

    pdf = tmp_path / "papers" / "2024_Leyn_NatureCommunications" / "2024_Leyn_NatureCommunications.pdf"
    assert pdf.read_bytes() == FAKE_PDF
