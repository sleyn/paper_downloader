# paper_downloader

Downloads open-access PDFs for the scientific papers in a paper list, using only public APIs.

## How it works

The tool reads each line of the paper list, extracts the DOI, and tries four strategies in order until one returns a PDF:

1. **Unpaywall** asks the Unpaywall API for the best open-access PDF URL.
2. **Europe PMC** searches EBI's Europe PMC REST API for a full-text PDF.
3. **Semantic Scholar** checks the Semantic Scholar graph API for an open-access PDF link.
4. **Direct DOI** follows the DOI URL and checks whether it returns a PDF.

A download counts only if it returns status 200, more than 1 KB, and a PDF content type or `%PDF` header, so an error page is never saved as a paper.
PubMed Central is not tried: its PDF links now serve a reCAPTCHA page ([ADR 0001](docs/adr/0001-drop-pubmed-central-strategy.md)).

Each PDF is saved in a paper folder named `<year>_<FirstAuthor>_<Journal>`, as `<output>/<folder>/<folder>.pdf`.
The paper metadata comes from Crossref (one request per paper): the issue year, the first author's family name (or the consortium name), and the full journal title with only letters and digits kept, e.g. `2024_Leyn_NatureCommunications`.
If Crossref lacks a field, the tool takes it from the citation line, then falls back to `0000` or `Unknown`. A citation line and a DOI line for the same paper get the same folder.
Two papers that would share a name get `_2`, `_3`, and so on.

## Install

You need [uv](https://docs.astral.sh/uv/). Python 3.10 or newer is required; uv fetches it if needed.

To run it from inside this repo:

```bash
uv sync
uv run paper-downloader --help
```

To install the `paper-downloader` command so it works from any directory:

```bash
uv tool install .
```

## Configuration

Unpaywall requires an email address, and it goes in every request's User-Agent. The tool takes the first one it finds from:

1. `--email you@example.com` on the command line
2. the `EMAIL` environment variable
3. `EMAIL=you@example.com` in a `.env` file in the current directory

With no email from any of these, it exits with an error.

## Usage

Run it from the folder that holds your paper list:

```bash
paper-downloader [options]          # installed with uv tool install
uv run paper-downloader [options]   # inside this repo
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `List_of_papers.txt` | Path to the paper list |
| `--output` | `papers` | Root directory for downloaded PDFs |
| `--delay` | `1.0` | Seconds to wait between HTTP requests |
| `--email` | *(see Configuration)* | Email for API requests |
| `--debug` | off | Print each HTTP request and response |

Both default paths are relative to the current directory.

## Input format

The paper list is a text file with one paper per line. Each line is one of:

- **Citation line**: a bibliographic citation with a DOI URL in it.
  ```
  Leyn SA, Kazanov MD, Suvorova IA, ... Nature Communications. 2024. https://doi.org/10.1038/s41467-024-12345-6
  ```
- **DOI line**: just a DOI, in any of these forms:
  ```
  https://doi.org/10.1038/s41467-024-12345-6
  http://dx.doi.org/10.1038/s41467-024-12345-6
  doi:10.1038/s41467-024-12345-6
  10.1038/s41467-024-12345-6
  ```
- **Comment**: a line starting with `#`. Ignored.
- **Blank line**: ignored.

Both kinds can be mixed in one list. Leading numbering (`12. `) and a period after the DOI are ignored.
After reading the list, the tool prints how many lines of each kind it found.
A line with text but no DOI is a **skipped line**: the tool lists each one with its line number and first 80 characters, and adds it to the failure log.

## Failure log

When a paper has no PDF from any strategy, or a line was skipped, the tool writes `<output>/failed_downloads.txt`.
Each entry is a `# reason` comment followed by your original line, unchanged:

```
# PDF not found via any strategy
2. doi:10.1000/missing
# no DOI found (line 3)
3. Smith J. A paper whose DOI I forgot to paste. Cell Reports. 2019.
```

The file is itself a paper list, so retrying only the failures is one command:

```bash
paper-downloader --input papers/failed_downloads.txt
```

After a run with no failures and no skipped lines, the tool deletes any old failure log.

## Output structure

```
papers/
  2024_Leyn_NatureCommunications/
    2024_Leyn_NatureCommunications.pdf
  failed_downloads.txt   # only written when some papers could not be fetched
```

## Development

```bash
uv sync          # creates .venv with runtime and dev dependencies
uv run pytest    # offline test suite; HTTP is faked with `responses`
```
