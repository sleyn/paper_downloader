# paper_downloader

Downloads open-access PDFs for scientific papers listed in a citation file.

## How it works

The script parses each line of the input file, extracts the DOI, and tries five download strategies in order:

1. **Unpaywall** — queries the Unpaywall API for the best open-access PDF URL
2. **Europe PMC** — searches EBI's Europe PMC REST API for a full-text PDF
3. **PubMed Central** — resolves the DOI to a PMC ID via NCBI eUtils, then fetches the PDF
4. **Semantic Scholar** — checks the Semantic Scholar graph API for an open-access PDF link
5. **Direct DOI** — follows the DOI URL directly and checks whether a PDF is returned

Each successfully downloaded paper is saved under `<output>/<year>_<FirstAuthor>_<JournalSlug>/<same-name>.pdf`.
Papers that could not be retrieved are logged to `<output>/failed_downloads.txt`.

## Requirements

Python 3.10+ and the following packages:

```
pip install requests python-dotenv
```

## Configuration

Create a `.env` file next to the script with your email address (required by Unpaywall and NCBI):

```
EMAIL=you@example.com
```

You can also pass `--email you@example.com` on the command line to override the `.env` value.

## Usage

Run from the repository root:

```bash
python reference/paper_scripts/download_papers.py [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `reference/List_of_papers.txt` | Path to the citation list |
| `--output` | `reference/papers` | Root directory for downloaded PDFs |
| `--delay` | `1.0` | Seconds to wait between HTTP requests |
| `--email` | *(from .env)* | Email for API requests |

## Input format

Each line should be a bibliographic citation ending with a `https://doi.org/…` URL, for example:

```
1. Leyn SA, Kazanov MD, Suvorova IA, ... Nature Communications. 2024. https://doi.org/10.1038/s41467-024-12345-6
```

Lines without a DOI URL are silently skipped.

## Output structure

```
reference/papers/
  2024_Leyn_NatureCommunications/
    2024_Leyn_NatureCommunications.pdf
  failed_downloads.txt   # only created when some papers could not be fetched
```
