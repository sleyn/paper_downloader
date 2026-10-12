"""Strategy waterfall: Unpaywall -> Europe PMC -> Semantic Scholar -> direct DOI."""

import re

import pytest
import requests

from fakes import FAKE_PDF, crossref_missing, crossref_url, unpaywall_hit

DOI = "10.1038/s41467-024-12345-6"
CITATION = f"Leyn SA. Things. Nature Communications. 2024. https://doi.org/{DOI}"
FOLDER = "2024_Leyn_NatureCommunications"

UNPAYWALL = f"https://api.unpaywall.org/v2/{DOI}"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
SEMANTIC_SCHOLAR = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{DOI}"
DIRECT_DOI = f"https://doi.org/{DOI}"
CROSSREF = crossref_url(DOI)


def requested_urls_without_query(http) -> list[str]:
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
    assert requested_urls_without_query(http) == [CROSSREF, UNPAYWALL, EUROPE_PMC, "https://europepmc.org/paper.pdf"]


def test_semantic_scholar_is_tried_right_after_europe_pmc(run, http):
    crossref_missing(http, DOI)
    http.get(UNPAYWALL, status=404)
    http.get(EUROPE_PMC, json={"resultList": {"result": []}})
    http.get(SEMANTIC_SCHOLAR, json={"openAccessPdf": {"url": "https://s2.example.org/paper.pdf"}})
    http.get("https://s2.example.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert requested_urls_without_query(http) == [CROSSREF, UNPAYWALL, EUROPE_PMC, SEMANTIC_SCHOLAR, "https://s2.example.org/paper.pdf"]


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


def test_direct_doi_fails_on_a_landing_page_without_pdf_links(run, http):
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


@pytest.mark.parametrize("error", [requests.ConnectionError("doi.org unreachable"), requests.ReadTimeout("doi.org timed out")])
def test_direct_doi_connection_error_or_timeout_fails_the_paper_and_the_run_continues(run, http, capsys, error):
    other = "10.1000/next"
    miss_all_apis(http)
    http.get(DIRECT_DOI, body=error)
    unpaywall_hit(http, other)
    crossref_missing(http, other)

    out = run([CITATION, other])

    assert not (out / FOLDER).exists()
    assert "PDF not found via any strategy" in (out / "failed_downloads.txt").read_text()
    assert "1 downloaded" in capsys.readouterr().out
    assert requested_urls_without_query(http).count(DIRECT_DOI) == 1


LANDING = "https://journal.example.org/article/12345"


def landing_page(http, body: str) -> None:
    """doi.org redirects to an HTML landing page holding `body`."""
    http.get(DIRECT_DOI, status=302, headers={"Location": LANDING})
    http.get(LANDING, body=f"<html><body>{body}</body></html>", content_type="text/html")


def test_direct_doi_follows_a_relative_pdf_link_on_the_landing_page(run, http):
    miss_all_apis(http)
    landing_page(http, '<a href="../files/12345.pdf">Download PDF</a>')
    http.get("https://journal.example.org/files/12345.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert "\tdirect_doi\t" in (out / "manifest.tsv").read_text()


def test_direct_doi_matches_pdf_links_case_insensitively(run, http):
    miss_all_apis(http)
    landing_page(http, '<a href="/article/12345/PDF/">Full text</a><a href="/files/12345.Pdf">Download</a>')
    http.get("https://journal.example.org/article/12345/PDF/", body="<html>" + "x" * 4096 + "</html>", content_type="text/html")
    http.get("https://journal.example.org/files/12345.Pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF


def test_direct_doi_tries_each_pdf_link_once_and_does_not_scan_html_candidates(run, http):
    miss_all_apis(http)
    landing_page(http, '<a href="/tiny.pdf">A</a><a href="/viewer/pdf">B</a>')
    http.get("https://journal.example.org/tiny.pdf", body=b"%PDF-1.4 tiny", content_type="application/pdf")
    http.get(
        "https://journal.example.org/viewer/pdf",
        body='<html><a href="/deeper.pdf">PDF</a>' + "x" * 4096 + "</html>",
        content_type="text/html",
    )

    out = run([CITATION])

    assert not (out / FOLDER).exists()
    assert "PDF not found via any strategy" in (out / "failed_downloads.txt").read_text()
    assert requested_urls_without_query(http)[-4:] == [
        DIRECT_DOI,
        LANDING,
        "https://journal.example.org/tiny.pdf",
        "https://journal.example.org/viewer/pdf",
    ]


def test_direct_doi_skips_non_http_links_and_tries_at_most_five_distinct_ones(run, http):
    miss_all_apis(http)
    links = [
        "javascript:openPdf()",
        "mailto:editor@example.org?subject=pdf",
        "#pdf-section",
        "/1.pdf",
        "/1.pdf",
        "https://journal.example.org/1.pdf",
        "/2.pdf",
        "/3.pdf",
        "/4.pdf",
        "/5.pdf",
        "/6.pdf",
    ]
    landing_page(http, "".join(f'<a href="{href}">PDF</a>' for href in links))
    http.get(re.compile(r"https://journal\.example\.org/\d\.pdf"), status=404)

    run([CITATION])

    assert requested_urls_without_query(http)[-6:] == [LANDING] + [f"https://journal.example.org/{n}.pdf" for n in range(1, 6)]


def test_direct_doi_debug_output_names_the_landing_page_and_each_candidate(run, http, capsys):
    miss_all_apis(http)
    landing_page(http, '<a href="/a.pdf">A</a><a href="/b.pdf">B</a>')
    http.get("https://journal.example.org/a.pdf", status=404)
    http.get("https://journal.example.org/b.pdf", body=FAKE_PDF, content_type="application/pdf")

    run([CITATION], "--debug")

    debug = [line.strip() for line in capsys.readouterr().out.splitlines() if "[direct_doi]" in line]
    assert any(LANDING in line for line in debug)
    assert any("https://journal.example.org/a.pdf" in line for line in debug)
    assert any("https://journal.example.org/b.pdf" in line for line in debug)


def test_direct_doi_tries_citation_pdf_url_before_links(run, http):
    miss_all_apis(http)
    landing_page(
        http,
        '<a href="/a.pdf">A</a><meta name="citation_pdf_url" content="/content/12345/download">',
    )
    http.get("https://journal.example.org/content/12345/download", status=403)
    http.get("https://journal.example.org/a.pdf", body=FAKE_PDF, content_type="application/pdf")

    out = run([CITATION])

    assert (out / FOLDER / f"{FOLDER}.pdf").read_bytes() == FAKE_PDF
    assert requested_urls_without_query(http)[-2:] == [
        "https://journal.example.org/content/12345/download",
        "https://journal.example.org/a.pdf",
    ]


def test_citation_pdf_url_is_deduplicated_with_links_and_counts_toward_the_limit(run, http):
    miss_all_apis(http)
    links = "".join(f'<a href="/{n}.pdf">PDF</a>' for n in range(1, 7))
    landing_page(http, f'<meta name="citation_pdf_url" content="https://journal.example.org/3.pdf">{links}')
    http.get(re.compile(r"https://journal\.example\.org/\d\.pdf"), status=404)

    run([CITATION])

    assert requested_urls_without_query(http)[-6:] == [
        LANDING,
        "https://journal.example.org/3.pdf",
        "https://journal.example.org/1.pdf",
        "https://journal.example.org/2.pdf",
        "https://journal.example.org/4.pdf",
        "https://journal.example.org/5.pdf",
    ]


def test_direct_doi_does_not_follow_links_on_an_error_page(run, http):
    miss_all_apis(http)
    http.get(DIRECT_DOI, status=302, headers={"Location": LANDING})
    http.get(LANDING, status=403, body='<html><a href="/a.pdf">PDF</a></html>', content_type="text/html")

    out = run([CITATION])

    assert not (out / FOLDER).exists()
    assert requested_urls_without_query(http)[-1] == LANDING
