"""Strategy waterfall: Unpaywall -> Europe PMC -> Semantic Scholar -> direct DOI."""

import re

from fakes import FAKE_PDF, crossref_missing, crossref_url

DOI = "10.1038/s41467-024-12345-6"
CITATION = f"Leyn SA. Things. Nature Communications. 2024. https://doi.org/{DOI}"
FOLDER = "2024_Leyn_NatureCommunications"

UNPAYWALL = f"https://api.unpaywall.org/v2/{DOI}"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SEMANTIC_SCHOLAR = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}"
DIRECT_DOI = f"https://doi.org/{DOI}"
CROSSREF = crossref_url(DOI)


def requested_hosts(http) -> list[str]:
    return [c.request.url.split("?")[0] for c in http.calls]


def test_europe_pmc_hit_stops_the_waterfall(run, http):
    crossref_missing(http, DOI)
    http.get(UNPAYWALL, status=404)
    http.get(
        EUROPE_PMC,
        json={"resultList": {"result": [{"fullTextUrlList": {"fullTextUrl": [
            {"documentStyle": "pdf", "url": "https://europepmc.org/paper.pdf"}
        ]}}]}},
    )
    http.get("https://europepmc.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert requested_hosts(http) == [CROSSREF, UNPAYWALL, EUROPE_PMC, "https://europepmc.org/paper.pdf"]


def test_semantic_scholar_is_tried_right_after_europe_pmc(run, http):
    crossref_missing(http, DOI)
    http.get(UNPAYWALL, status=404)
    http.get(EUROPE_PMC, json={"resultList": {"result": []}})
    http.get(SEMANTIC_SCHOLAR, json={"openAccessPdf": {"url": "https://s2.example.org/paper.pdf"}})
    http.get("https://s2.example.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert requested_hosts(http) == [CROSSREF, UNPAYWALL, EUROPE_PMC, SEMANTIC_SCHOLAR, "https://s2.example.org/paper.pdf"]


def miss_all_apis(http):
    crossref_missing(http, DOI)
    http.get(UNPAYWALL, status=404)
    http.get(EUROPE_PMC, json={"resultList": {"result": []}})
    http.get(SEMANTIC_SCHOLAR, status=404)


def test_direct_doi_rejects_a_tiny_pdf_body(run, http):
    miss_all_apis(http)
    http.get(DIRECT_DOI, body=b"%PDF-1.4 tiny", content_type="application/pdf")

    out = run([CITATION])

    assert not (out / FOLDER).exists()
    assert "PDF not found via any strategy" in (out / "failed_downloads.txt").read_text()


def test_direct_doi_rejects_an_html_landing_page(run, http):
    miss_all_apis(http)
    http.get(DIRECT_DOI, body="<html>" + "x" * 4096 + "</html>", content_type="text/html")

    out = run([CITATION])

    assert not (out / FOLDER).exists()


def test_direct_doi_accepts_a_real_pdf(run, http):
    miss_all_apis(http)
    http.get(DIRECT_DOI, body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF


def test_dois_with_special_characters_are_encoded_in_every_request(run, http):
    odd_doi = "10.1002/abc#d;e<f>g"
    for host in ("api.crossref.org", "api.unpaywall.org", "www.ebi.ac.uk", "api.semanticscholar.org", "doi.org"):
        http.get(re.compile(rf"https://{re.escape(host)}/.*"), status=404)

    run([f"Leyn SA. Things. Nature Communications. 2024. https://doi.org/{odd_doi}"])

    assert [c.request.url for c in http.calls] == [
        "https://api.crossref.org/works/10.1002/abc%23d%3Be%3Cf%3Eg?mailto=test%40example.com",
        "https://api.unpaywall.org/v2/10.1002/abc%23d%3Be%3Cf%3Eg?email=test%40example.com",
        (
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
            "?query=DOI%3A10.1002%2Fabc%23d%3Be%3Cf%3Eg&format=json&resultType=core"
        ),
        "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1002/abc%23d%3Be%3Cf%3Eg?fields=openAccessPdf",
        "https://doi.org/10.1002/abc%23d%3Be%3Cf%3Eg",
    ]
