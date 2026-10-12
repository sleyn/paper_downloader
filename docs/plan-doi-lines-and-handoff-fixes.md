# Plan: DOI lines + handoff fixes

Agreed 2026-10-11. Resolves all 11 findings from the handoff doc and adds DOI lines as input.
Terms follow [GLOSSARY.md](../GLOSSARY.md).

## Decisions

| # | Decision |
|---|---|
| Q1 | Fast-forward `main` to `fix-email-handling`, then work on a new branch `doi-input-and-fixes`. |
| Q2 | Defaults: `--input List_of_papers.txt`, `--output papers` (relative to the current directory). `papers/` is git-ignored. |
| Q3 | Drop the PubMed Central strategy; four strategies remain ([ADR 0001](adr/0001-drop-pubmed-central-strategy.md)). |
| Q4 | Reword the help text; no supplementary downloads. |
| Q5 | Delete `fetch_landing_html` and the discarded landing-page HTML. |
| Q6 | Each line is classified on its own: citation line, DOI line (`https://doi.org/…`, `http://dx.doi.org/…`, `doi:…`, bare `10.…`), blank, or `#` comment. Leading numbering is stripped. |
| Q7 | Paper metadata comes from Crossref for every paper. Citation text is the fallback, then `0000_Unknown_Unknown`. |
| Q8 | Skipped lines are printed in a warning block and written to the failure log. |
| Q9 | The repo becomes a uv package with offline pytest tests. There is one test seam: `main(argv)`, with HTTP faked by `responses`. |
| Q10 | `src/paper_downloader/` holding `parsing.py`, `metadata.py`, `strategies.py` and `cli.py`; console script `paper-downloader`; `uv_build` backend. |
| Q11 | Email: `--email` overrides the `EMAIL` environment variable, which overrides `.env` in the current directory. |
| Q12 | `requires-python = ">=3.10"`; pytest goes in the `dev` dependency group; `uv.lock` is committed. |
| Q13 | `papers/manifest.tsv` (doi, folder, strategy, date). A paper whose DOI is listed and whose PDF exists is skipped. `--force` re-downloads. |
| Q14 | Failure log = a `# reason` line followed by the original line, so it can be fed back in with `--input`. An old failure log is deleted after a clean run. |
| Q15 | Folder journal names use Crossref's full `container-title`. |

## Steps (one commit each)

1. **Branch.** `git switch main && git merge --ff-only fix-email-handling && git switch -c doi-input-and-fixes`.
2. **Package scaffold.** Add `pyproject.toml` (dependencies requests and python-dotenv; `[dependency-groups] dev = ["pytest"]`; `[project.scripts] paper-downloader = "paper_downloader.cli:main"`). Move the code into `src/paper_downloader/` with no behaviour change, then `uv lock`. Add `papers/` to `.gitignore`. Covers findings 11 and 5 (paths).
3. **Parsing, tests first.** Test: citation lines (including titles and journals that contain periods, finding 10), the four DOI-line forms, numbering, comments, blanks, skipped lines, and trailing-period stripping. Then rewrite `parse_line` to return a line kind plus the DOI and the fallback metadata.
4. **Crossref metadata.** `fetch_metadata(doi, session)`: year from `issued.date-parts`, first author from `author[0].family` (or `name` for a consortium), journal from `container-title[0]`. Send `mailto=EMAIL`. Tests use canned JSON. Fallback order: citation values, then `Unknown` / `0000`.
5. **Strategies.** Remove `try_pubmed_central` (finding 1). Pass query values through `params=` and path DOIs through `quote(doi, safe="/")` (finding 2). `try_direct_doi` returns bytes only and uses the `download_url` checks (findings 3 and 8). Remove the f-string prefix that does nothing (finding 9).
6. **Manifest and skip.** Load the manifest at start. Skip papers that are listed and present, before any Crossref call. Seed `unique_name` with the folder names already in the manifest. Append one row after each save. Add `--force` (finding 4).
7. **Failure log and warnings.** Print skipped lines after parsing. Write the failure log in its new re-runnable format, and delete the old one after a clean run (finding 7).
8. **CLI.** New defaults, email resolution order, reworded description (finding 6), four-step waterfall.
9. **Docs.** README: `uv sync`, `uv run paper-downloader`, `uv tool install .`, input formats, manifest, re-running the failure log. CLAUDE.md: four strategies, new paths, `.env` read from the current directory, `uv run pytest`, links to the glossary and ADRs.
10. **Verify.** Run `uv run pytest`. Then a live smoke test with a paper list of 4–5 lines mixing citation and DOI lines: run it twice to confirm skipping, then run once on the failure log.
