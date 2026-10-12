# paper_scripts — Claude instructions

## Purpose
This directory contains `download_papers.py`, a standalone script that fetches open-access PDFs for papers in `reference/List_of_papers.txt` using five public APIs (Unpaywall, Europe PMC, PubMed Central, Semantic Scholar, direct DOI).

## Running the script
Always run from the **repository root** (the `AI_Job_Helper` directory), not from inside `paper_scripts/`:

```bash
python reference/paper_scripts/download_papers.py
```

The default `--input` and `--output` paths are relative to the repository root.

## Key implementation details

- `EMAIL` is read from `.env` next to the script at module load time; `--email` overrides it in `main()`. If neither provides an email, the script exits. `HEADERS["User-Agent"]` is set in `main()` after `EMAIL` is final.
- Download strategies are tried in order: Unpaywall → Europe PMC → PubMed Central → Semantic Scholar → direct DOI. A strategy returning `None` means no PDF was found; the next one is tried.
- `try_pubmed_central` adds an extra `time.sleep(0.35)` between the eUtils search and the PDF fetch to stay within NCBI rate limits (3 req/s without an API key).
- Folder names are sanitised: `{year}_{FirstAuthor}_{JournalNoSpecialChars}`. Duplicate base names get a `_2`, `_3`, … suffix via `unique_name()`.
- `failed_downloads.txt` is only written when at least one paper fails; it records the DOI URL, reason, and original citation line.

## When modifying this script

- Keep the five-strategy waterfall pattern. Do not collapse strategies into a single function — each one targets a different API with different response shapes.
- The `EMAIL` global is intentionally mutable (overridden via `--email`). Do not convert it to a constant.
- Avoid adding retry loops inside individual `try_*` functions; rate-limit handling belongs at the `process_paper` level via `--delay`.
- Test with a small subset of `List_of_papers.txt` by passing a truncated copy to `--input` to avoid hammering APIs during development.
