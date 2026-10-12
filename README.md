# paper_downloader

Downloads open-access PDFs for the scientific papers in a paper list, using only public APIs.

## How it works

The tool reads each line of the paper list, extracts the DOI, and tries five strategies in order until one returns a PDF:

1. **Unpaywall** asks the Unpaywall API for the best open-access PDF URL.
2. **Europe PMC** searches EBI's Europe PMC REST API for a full-text PDF.
3. **PubMed Central** resolves the DOI to a PMC ID with NCBI eUtils, then fetches the PDF.
4. **Semantic Scholar** checks the Semantic Scholar graph API for an open-access PDF link.
5. **Direct DOI** follows the DOI URL and checks whether it returns a PDF.

Each PDF is saved as `<output>/<year>_<FirstAuthor>_<JournalSlug>/<same-name>.pdf`.
Papers with no PDF found are logged to `<output>/failed_downloads.txt`.

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

Unpaywall and NCBI require an email address. The tool takes the first one it finds from:

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

Each line is a bibliographic citation ending with a `https://doi.org/…` URL, for example:

```
1. Leyn SA, Kazanov MD, Suvorova IA, ... Nature Communications. 2024. https://doi.org/10.1038/s41467-024-12345-6
```

Lines without a DOI URL are skipped without a warning.

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
