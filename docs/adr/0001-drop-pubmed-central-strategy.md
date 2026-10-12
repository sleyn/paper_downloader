# Drop the PubMed Central strategy

PubMed Central PDF URLs now redirect to `pmc.ncbi.nlm.nih.gov`, which serves a Google reCAPTCHA challenge instead of the PDF (checked 2026-10-11). The obvious alternatives also failed: Europe PMC's `?pdf=render` returned 403, and the PMC OA web service (`oa.fcgi`) returned 404. We removed the strategy and went from five strategies to four, because Europe PMC already returns PMC-hosted full text for most papers.

## Considered Options

- **PMC Open Data bucket on AWS S3**: works, but it only covers the OA subset and needs a PMCID lookup plus S3 listing logic. Revisit this if Europe PMC misses many PMC papers.
