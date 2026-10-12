"""Paper folder names from Crossref paper metadata, with citation text and Unknown as fallbacks."""

import shutil
from urllib.parse import parse_qs, urlparse

from fakes import FAKE_PDF, crossref_missing, crossref_record, unpaywall_hit

DOI = "10.1038/s41467-024-12345-6"


def folders(out) -> list[str]:
    return sorted(p.name for p in out.iterdir() if p.is_dir())


def test_doi_line_folder_named_from_crossref(run, http):
    crossref_record(http, DOI, year=2024, family="Leyn", journal="Nature Communications")
    unpaywall_hit(http, DOI)

    out = run([DOI], email="me@example.com")

    folder = "2024_Leyn_NatureCommunications"
    assert (out / folder / f"{folder}.pdf").read_bytes() == FAKE_PDF
    crossref_call = http.calls[0].request.url
    assert crossref_call.startswith(f"https://api.crossref.org/works/{DOI}?")
    assert parse_qs(urlparse(crossref_call).query)["mailto"] == ["me@example.com"]


def test_consortium_author_name_used_when_no_family_name(run, http):
    crossref_record(http, DOI, year=2021, name="COVID-19 Genomics Consortium", journal="The Lancet")
    unpaywall_hit(http, DOI)

    out = run([DOI])

    assert folders(out) == ["2021_COVID-19GenomicsConsortium_TheLancet"]


def test_crossref_404_falls_back_to_citation_values(run, http):
    crossref_missing(http, DOI)
    unpaywall_hit(http, DOI)

    out = run([f"Smith J. A study. Cell Reports. 2019. https://doi.org/{DOI}"])

    assert folders(out) == ["2019_Smith_CellReports"]


def test_partial_crossref_record_filled_from_citation(run, http):
    crossref_record(http, DOI, year=2020, journal="Nature Communications")
    unpaywall_hit(http, DOI)

    out = run([f"Smith J. A study. Nat Commun. 2019. https://doi.org/{DOI}"])

    assert folders(out) == ["2020_Smith_NatureCommunications"]


def test_doi_line_with_crossref_down_gets_unknown_folder(run, http):
    crossref_missing(http, DOI, status=503)
    unpaywall_hit(http, DOI)

    out = run([DOI])

    assert folders(out) == ["0000_Unknown_Unknown"]


def test_citation_line_and_doi_line_for_same_doi_get_same_folder(run, http):
    names = []
    for line in (f"Leyn SA. Things. Nat Commun. 2024. https://doi.org/{DOI}", f"doi:{DOI}"):
        crossref_record(http, DOI, year=2024, family="Leyn", journal="Nature Communications")
        unpaywall_hit(http, DOI)
        out = run([line])
        names.append(folders(out))
        shutil.rmtree(out)

    assert names == [["2024_Leyn_NatureCommunications"], ["2024_Leyn_NatureCommunications"]]


def test_periods_in_title_and_journal_do_not_break_the_folder_name(run, http):
    doi = "10.1073/pnas.123"
    crossref_record(http, doi, year=2020, family="Smith", journal="Proceedings of the National Academy of Sciences")
    unpaywall_hit(http, doi)

    out = run([f"Smith J. Fe vs. Cu in E. coli. Proc. Natl. Acad. Sci. U.S.A. 2020. https://doi.org/{doi}"])

    assert folders(out) == ["2020_Smith_ProceedingsoftheNationalAcademyofSciences"]


def test_debug_prints_crossref_lookup_and_resolved_metadata(run, http, capsys):
    crossref_record(http, DOI, year=2024, family="Leyn", journal="Nature Communications")
    unpaywall_hit(http, DOI)

    run([DOI], "--debug")

    console = capsys.readouterr().out
    assert f"[crossref] https://api.crossref.org/works/{DOI}" in console
    assert "year='2024'" in console and "first_author='Leyn'" in console
