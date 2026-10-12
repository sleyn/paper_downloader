"""End-to-end downloads through the CLI."""

from conftest import FAKE_PDF

from paper_downloader import cli

CITATION = (
    "1. Leyn SA, Kazanov MD, Suvorova IA. A study of things. Nature Communications. 2024. "
    "https://doi.org/10.1038/s41467-024-12345-6"
)


def test_citation_line_saved_from_unpaywall(run, http):
    http.get(
        "https://api.unpaywall.org/v2/10.1038/s41467-024-12345-6",
        json={"best_oa_location": {"url_for_pdf": "https://oa.example.org/paper.pdf"}},
    )
    http.get("https://oa.example.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    pdf = out / "2024_Leyn_NatureCommunications" / "2024_Leyn_NatureCommunications.pdf"
    assert pdf.read_bytes() == FAKE_PDF
    assert not (out / "failed_downloads.txt").exists()


def test_defaults_read_list_and_write_papers_in_current_directory(tmp_path, http):
    http.get(
        "https://api.unpaywall.org/v2/10.1038/s41467-024-12345-6",
        json={"best_oa_location": {"url_for_pdf": "https://oa.example.org/paper.pdf"}},
    )
    http.get("https://oa.example.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")
    (tmp_path / "List_of_papers.txt").write_text(CITATION + "\n", encoding="utf-8")

    cli.main(["--delay", "0", "--email", "test@example.com"])

    pdf = tmp_path / "papers" / "2024_Leyn_NatureCommunications" / "2024_Leyn_NatureCommunications.pdf"
    assert pdf.read_bytes() == FAKE_PDF
