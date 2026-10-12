"""Download strategies: one function per open-access source, plus the shared download helper."""

from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import requests

# Set by cli.main() once the email is resolved; intentionally mutable.
EMAIL = ""

_debug = False

# Most links tried from one landing page.
MAX_PDF_CANDIDATES = 5

# User-Agent is filled in by cli.main() once EMAIL is final.
HEADERS: dict[str, str] = {}


def quote_doi(doi: str) -> str:
    """Percent-encode a DOI for use in a URL path, keeping its `/` separators."""
    return quote(doi, safe="/")


def pdf_bytes(r: requests.Response) -> bytes | None:
    """Return the body if the response is a PDF: status 200, more than 1 KB, and a PDF content type or `%PDF` header."""
    ct = r.headers.get("Content-Type", "")
    if r.status_code == 200 and len(r.content) > 1024:
        if "pdf" in ct or r.content[:4] == b"%PDF":
            return r.content
    return None


def download_url(url: str, session: requests.Session, timeout: int = 30) -> bytes | None:
    try:
        r = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if _debug:
            ct = r.headers.get("Content-Type", "")
            print(f"    [download_url] {url} → status={r.status_code} content-type={ct!r} size={len(r.content)} header={r.content[:8]!r}")
        return pdf_bytes(r)
    except Exception as e:
        if _debug:
            print(f"    [download_url] exception: {e}")
    return None


def try_unpaywall(doi: str, session: requests.Session) -> bytes | None:
    try:
        url = f"https://api.unpaywall.org/v2/{quote_doi(doi)}"
        r = session.get(url, params={"email": EMAIL}, headers=HEADERS, timeout=15)
        if _debug:
            print(f"  [unpaywall] status={r.status_code}")
        if r.status_code != 200:
            return None
        data = r.json()
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        if _debug:
            print(f"  [unpaywall] best_oa_location pdf_url={pdf_url}")
        if pdf_url:
            result = download_url(pdf_url, session)
            if result:
                return result
        for loc in data.get("oa_locations", []):
            pdf_url = loc.get("url_for_pdf") or loc.get("url")
            if _debug:
                print(f"  [unpaywall] trying oa_location pdf_url={pdf_url}")
            if pdf_url:
                result = download_url(pdf_url, session)
                if result:
                    return result
    except Exception as e:
        if _debug:
            print(f"  [unpaywall] exception: {e}")
    return None


def try_europe_pmc(doi: str, session: requests.Session) -> bytes | None:
    try:
        search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {"query": f"DOI:{doi}", "format": "json", "resultType": "core"}
        r = session.get(search_url, params=params, headers=HEADERS, timeout=15)
        if _debug:
            print(f"  [europe_pmc] status={r.status_code}")
        if r.status_code != 200:
            return None
        results = r.json().get("resultList", {}).get("result", [])
        if _debug:
            print(f"  [europe_pmc] results={len(results)}")
        for item in results:
            full_text_url_list = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
            for full_text_url in full_text_url_list:
                if full_text_url.get("documentStyle") == "pdf":
                    pdf_url = full_text_url.get("url")
                    if _debug:
                        print(f"  [europe_pmc] trying pdf_url={pdf_url}")
                    result = download_url(pdf_url, session)
                    if result:
                        return result
    except Exception as e:
        if _debug:
            print(f"  [europe_pmc] exception: {e}")
    return None


def try_semantic_scholar(doi: str, session: requests.Session) -> bytes | None:
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote_doi(doi)}"
        r = session.get(url, params={"fields": "openAccessPdf"}, headers=HEADERS, timeout=15)
        if _debug:
            print(f"  [semantic_scholar] status={r.status_code}")
        if r.status_code != 200:
            return None
        oa = r.json().get("openAccessPdf") or {}
        pdf_url = oa.get("url")
        if _debug:
            print(f"  [semantic_scholar] pdf_url={pdf_url}")
        if pdf_url:
            return download_url(pdf_url, session)
    except Exception as e:
        if _debug:
            print(f"  [semantic_scholar] exception: {e}")
    return None


class _LandingPageParser(HTMLParser):
    """Collect `citation_pdf_url` meta values and `<a href>` values that mention "pdf", in page order."""

    def __init__(self) -> None:
        super().__init__()
        self.meta_urls: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        content = values.get("content")
        if tag == "meta" and (values.get("name") or "").lower() == "citation_pdf_url" and content:
            self.meta_urls.append(content)
        href = values.get("href")
        if tag == "a" and href and "pdf" in href.lower():
            self.links.append(href)


def pdf_candidates(html: str, base_url: str) -> list[str]:
    """Return up to MAX_PDF_CANDIDATES distinct PDF URLs on a landing page, `citation_pdf_url` first, resolved against `base_url`."""
    parser = _LandingPageParser()
    parser.feed(html)
    candidates: list[str] = []
    for href in parser.meta_urls + parser.links:
        href = href.strip()
        if href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            continue
        url = urljoin(base_url, href)
        if url not in candidates:
            candidates.append(url)
    return candidates[:MAX_PDF_CANDIDATES]


def try_direct_doi(doi: str, session: requests.Session) -> bytes | None:
    try:
        doi_url = f"https://doi.org/{quote_doi(doi)}"
        r = session.get(doi_url, headers=HEADERS, timeout=30, allow_redirects=True)
        if _debug:
            print(f"  [direct_doi] {doi_url} → status={r.status_code} content-type={r.headers.get('Content-Type', '')!r}")
        pdf = pdf_bytes(r)
        if pdf or r.status_code != 200:
            return pdf
        candidates = pdf_candidates(r.text, r.url)
        if _debug:
            print(f"  [direct_doi] landing page {r.url}: {len(candidates)} PDF link(s)")
        for url in candidates:
            if _debug:
                print(f"  [direct_doi] trying {url}")
            pdf = download_url(url, session)
            if pdf:
                return pdf
    except Exception as e:
        if _debug:
            print(f"  [direct_doi] exception: {e}")
    return None
