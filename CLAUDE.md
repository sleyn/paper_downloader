# paper_downloader: Claude instructions

## Purpose
A uv package with one console script, `paper-downloader`, that fetches open-access PDFs for the papers in a paper list using public APIs (Unpaywall, Europe PMC, Semantic Scholar, direct DOI). Domain terms are defined in `GLOSSARY.md`; decisions live in `docs/adr/`.

## Workflow

```bash
uv sync                      # install runtime + dev dependencies
uv run paper-downloader      # run against ./List_of_papers.txt, writing to ./papers
uv run pytest                # offline test suite
```

Default `--input` and `--output` are relative to the current directory.

## Layout
`src/paper_downloader/`: `parsing.py` (line parsing), `metadata.py` (paper folder naming), `strategies.py` (one function per strategy plus `download_url`), `cli.py` (arguments, email resolution, the per-paper waterfall).

## Key implementation details

- Email resolution happens in `cli.main()`: `--email`, then the `EMAIL` environment variable, then `EMAIL` in `.env` in the current directory. No email exits with an error. The result goes into `strategies.EMAIL`, and `strategies.HEADERS["User-Agent"]` is set after it.
- `cli.WATERFALL` lists the strategies in order: Unpaywall → Europe PMC → Semantic Scholar → direct DOI. Each takes `(doi, session)` and returns PDF bytes, or `None` to pass to the next one. PubMed Central was dropped because it serves a reCAPTCHA page ([ADR 0001](docs/adr/0001-drop-pubmed-central-strategy.md)); keep it out unless that ADR is superseded.
- Every PDF goes through `strategies.download_url`, which accepts only status 200, more than 1 KB, and a PDF content type or `%PDF` header.
- DOIs in URL paths go through `quote_doi` (percent-encoded, `/` kept); query values go through `params=`.
- Paper folders are named `{year}_{FirstAuthor}_{JournalNoSpecialChars}`. Duplicate names get `_2`, `_3`, … from `unique_name()`.
- `failed_downloads.txt` is written only when at least one paper fails. It records the DOI URL, reason, and original citation line.

## When modifying the code

- Keep the strategy waterfall: each strategy stays its own function, because each targets a different API with a different response shape.
- `strategies.EMAIL` is intentionally a mutable module global set by `cli.main()`. Keep it a global.
- Rate-limit handling belongs at the `process_paper` level via `--delay`; keep `try_*` functions single-attempt, with no retry loops.

## Tests
Every test calls `cli.main(argv)`. The `run` fixture in `tests/conftest.py` builds the usual argv: a temporary paper list and output directory, `--delay 0` and `--email`. Tests of defaults or `--help` call `cli.main` directly. The autouse `http` fixture fakes HTTP with `responses`, so an unregistered URL fails any test. Assert only on visible results (files written, request URLs, console output, exit), never on internal helpers. For a live check, pass a short paper list with `--input` rather than a full list.
