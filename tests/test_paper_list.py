"""Reading a paper list: citation lines, DOI lines, comments, blanks and numbering."""

import pytest
from fakes import FAKE_PDF, crossref_missing, unpaywall_hit

DOI = "10.1038/s41467-024-12345-6"
UNKNOWN = "0000_Unknown_Unknown"


def folders(out) -> list[str]:
    return sorted(p.name for p in out.iterdir() if p.is_dir())


@pytest.mark.parametrize(
    "line",
    [
        f"https://doi.org/{DOI}",
        f"http://dx.doi.org/{DOI}",
        f"doi:{DOI}",
        DOI,
    ],
)
def test_each_doi_line_form_downloads_its_paper(run, http, line):
    crossref_missing(http, DOI)
    unpaywall_hit(http, DOI)

    out = run([line])

    assert (out / UNKNOWN / f"{UNKNOWN}.pdf").read_bytes() == FAKE_PDF


def test_mixed_numbered_list_with_comments_and_blanks(run, http, capsys):
    for doi in ("10.1000/aaa", "10.1000/bbb", "10.1000/ccc"):
        crossref_missing(http, doi)
        unpaywall_hit(http, doi)

    out = run([
        "# Papers for the review",
        "",
        "1. Leyn SA. Things. Nature Communications. 2024. https://doi.org/10.1000/aaa.",
        "2. doi:10.1000/bbb.",
        "3. 10.1000/ccc",
    ])

    assert folders(out) == [
        UNKNOWN,
        f"{UNKNOWN}_2",
        "2024_Leyn_NatureCommunications",
    ]
    unpaywall_dois = [c.request.url.split("/v2/")[1].split("?")[0] for c in http.calls if "unpaywall" in c.request.url]
    assert unpaywall_dois == ["10.1000/aaa", "10.1000/bbb", "10.1000/ccc"]
    console = capsys.readouterr().out
    assert "1 citation line, 2 DOI lines, 0 skipped lines, 1 comment, 1 blank line" in console
    assert "warning" not in console.lower()


def test_doi_url_is_always_https_doi_org(run, http, capsys):
    crossref_missing(http, DOI)
    unpaywall_hit(http, DOI)

    run([f"http://dx.doi.org/{DOI}"])

    assert f"DOI: https://doi.org/{DOI}" in capsys.readouterr().out
