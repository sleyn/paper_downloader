# Direct DOI follows PDF links on the landing page

Many publishers resolve a DOI to a landing page rather than a PDF, so the direct DOI strategy now parses that page with the standard library `html.parser` and tries its `citation_pdf_url` meta tag, then up to 5 links containing "pdf", one level deep, still recorded as `direct_doi`. It makes a single GET on `doi.org` and shares the PDF acceptance check with `download_url`, so the page is never fetched twice. Getting past bot walls (403s, Cloudflare challenges) is out of scope.

## Considered Options

- **BeautifulSoup or lxml**: more robust parsing, but a new dependency for a few tags that `html.parser` finds fine.
- **Following links more than one level deep**: catches PDF viewer pages, but multiplies requests per paper and risks crawling the publisher's site.
- **Getting past bot walls**: would need a browser-like User-Agent or a headless browser. The User-Agent stays the same, and those pages fail the paper as before.
