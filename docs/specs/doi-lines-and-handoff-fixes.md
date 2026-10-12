# Spec: DOI lines, reliable re-runs, and handoff fixes

Labels: `ready-for-agent`
Vocabulary: [GLOSSARY.md](../../GLOSSARY.md). Decisions: [ADR 0001](../adr/0001-drop-pubmed-central-strategy.md). Step plan: [plan](../plan-doi-lines-and-handoff-fixes.md).

## Problem Statement

I keep lists of papers I want as PDFs. Often I only have the DOI links, not full citations. The downloader only accepts citation lines that end in a `https://doi.org/…` URL, and drops anything else without a word. So a list of bare DOIs downloads nothing and gives no hint why.

Using it is also unreliable in other ways:

- Every run downloads every paper again.
- The PubMed Central step can never succeed, because PMC now answers with a reCAPTCHA page.
- A DOI with special characters breaks the API requests.
- A tiny error page from the direct-DOI step can be saved as if it were the paper.
- Folder names depend on regex parsing of citation text, which breaks when a title or journal contains a period.
- The default paths and the run instructions point at a directory layout from another repo.
- The help text promises supplementary files that it never downloads.
- There's no package metadata, no lockfile and no tests, so I can't install the tool cleanly or change it safely.

## Solution

I can give the downloader a paper list that mixes citation lines and DOI lines in any common DOI form. It works out each paper's metadata from Crossref, so a paper gets the same paper folder whichever way it's listed.

The tool:

- Skips papers already in the manifest, unless I pass `--force`.
- Tells me which lines were skipped and why.
- Writes a failure log that I can pass straight back as the next paper list.

It's a uv package with a `paper-downloader` command, sensible defaults relative to where I run it, four working strategies, and an offline test suite.

## User Stories

1. As a researcher, I want to list papers by DOI alone, so that I don't have to find and paste full citations.
2. As a researcher, I want `https://doi.org/…` DOI lines to work, so that I can paste links copied from a browser.
3. As a researcher, I want `http://dx.doi.org/…` DOI lines to work, so that old-style links from older sources are accepted.
4. As a researcher, I want `doi:10.…` DOI lines to work, so that DOIs copied from PDFs and reference managers are accepted.
5. As a researcher, I want bare `10.…` DOI lines to work, so that DOIs exported from spreadsheets are accepted.
6. As a researcher, I want to mix citation lines and DOI lines in one paper list, so that I don't have to keep two files.
7. As a researcher, I want numbered lines (`12. …`) to work in either form, so that numbered bibliographies can be pasted in as they are.
8. As a researcher, I want lines starting with `#` to be ignored, so that I can annotate or temporarily disable entries.
9. As a researcher, I want blank lines to be ignored, so that I can group my list visually.
10. As a researcher, I want a trailing period after a DOI to be ignored, so that DOIs at the end of a citation sentence still resolve.
11. As a researcher, I want each paper folder named `{year}_{FirstAuthor}_{Journal}` from Crossref metadata, so that folders sort and read well even for DOI lines.
12. As a researcher, I want the same paper to get the same paper folder whether I listed it as a citation line or a DOI line, so that I never get duplicate downloads.
13. As a researcher, I want folder names to be right even when a title or journal contains periods, so that folders aren't named after a fragment of the title.
14. As a researcher, I want the journal part of a folder name to come from the full journal title, so that names stay readable (`NatureCommunications`, not `NatCommun`).
15. As a researcher, I want a consortium author's name used when there's no personal first author, so that consortium papers still get a meaningful folder.
16. As a researcher, I want the citation text used as metadata when Crossref has no record, so that citation lines still get good names for DOIs Crossref doesn't know.
17. As a researcher, I want a `0000_Unknown_Unknown` folder (with a numeric suffix if needed) when no metadata is available anywhere, so that the PDF is still saved.
18. As a researcher, I want two different papers that would share a folder name to get `_2`, `_3` suffixes, so that neither overwrites the other.
19. As a researcher, I want new papers' suffixes to account for paper folders from earlier runs, so that a new paper never collides with one already on disk.
20. As a researcher, I want papers already in the manifest, with their PDF present, to be skipped on a re-run, so that re-running a growing list is fast and doesn't load the APIs.
21. As a researcher, I want skipped papers to cost no network request at all, Crossref included, so that a re-run of a long list finishes quickly.
22. As a researcher, I want a paper whose manifest entry exists but whose PDF was deleted to be downloaded again, so that I can recover a lost file by deleting it and re-running.
23. As a researcher, I want `--force` to re-download every paper, so that I can refresh PDFs that might have changed.
24. As a researcher, I want the manifest to record each paper's DOI, paper folder, the strategy that succeeded and the date, so that I can see where each PDF came from.
25. As a researcher, I want each manifest row written as soon as its PDF is saved, so that an interrupted run doesn't lose track of finished downloads.
26. As a researcher, I want lines with content but no DOI listed in a warning after parsing, with line number and the start of the line, so that I can fix typos in my list.
27. As a researcher, I want skipped lines included in the failure log too, so that I have one place to see everything that needs attention.
28. As a researcher, I want each failure log entry to be a `# reason` comment followed by my original line unchanged, so that I can read why it failed and still re-run it.
29. As a researcher, I want to pass the failure log back with `--input`, so that retrying only the failures is one command.
30. As a researcher, I want an old failure log deleted after a run with no failures, so that a stale log never misleads me.
31. As a researcher, I want a summary of how many papers were downloaded, skipped as already present, and failed, so that I know the outcome at a glance.
32. As a researcher, I want DOIs with characters such as `#`, `;`, `<` or `>` to be requested correctly, so that unusual DOIs don't fail for no reason.
33. As a researcher, I want the direct-DOI strategy to reject tiny or non-PDF responses, so that an error page is never saved as my paper.
34. As a researcher, I want the downloader to stop trying PubMed Central, so that every paper isn't slowed by a request that can never succeed.
35. As a researcher, I want strategies tried in the fixed order Unpaywall → Europe PMC → Semantic Scholar → direct DOI, so that the most reliable sources are tried first.
36. As a researcher, I want `--delay` to apply to every request, Crossref included, so that I control how hard the tool hits public APIs.
37. As a researcher, I want to install the tool with `uv tool install .` and run it as `paper-downloader`, so that I can use it from any directory.
38. As a researcher, I want to run it with `uv run paper-downloader` inside the repo, so that I don't need a global install while developing.
39. As a researcher, I want the defaults `List_of_papers.txt` and `papers/` relative to my current directory, so that the bare command works in a project folder.
40. As a researcher, I want my email read from `.env` in the current directory, so that an installed tool still finds my configuration.
41. As a researcher, I want an `EMAIL` environment variable to work too, so that I can configure it in my shell or in CI.
42. As a researcher, I want `--email` to override both, so that I can switch addresses for one run.
43. As a researcher, I want the tool to exit with a clear message when no email is configured, so that I never send anonymous requests to Unpaywall, NCBI or Crossref.
44. As a researcher, I want my email sent to Crossref as its `mailto` parameter, so that my requests use Crossref's polite pool.
45. As a researcher, I want the help text to describe only what the tool does, so that I don't look for supplementary files that never arrive.
46. As a researcher, I want `--debug` to show the Crossref lookup and each strategy's requests, so that I can diagnose a paper that keeps failing.
47. As a developer, I want a pinned lockfile in the repo, so that every machine runs the same dependency versions.
48. As a developer, I want `uv run pytest` to run an offline test suite, so that I can change parsing and naming safely without touching live APIs.
49. As a developer, I want `papers/` git-ignored, so that downloaded PDFs are never committed by accident.
50. As a developer, I want README and CLAUDE.md to describe the four strategies, the input forms, the manifest, the failure log and the uv workflow, so that the docs match the code.
51. As a developer, I want the PubMed Central removal recorded in an ADR, so that nobody adds back a step that can't work.

## Implementation Decisions

- **Packaging.** The repo becomes a uv package: `src` layout, package `paper_downloader`, `uv_build` backend, `requires-python >= 3.10`. Runtime dependencies are requests and python-dotenv. A `dev` dependency group holds pytest and responses. The console script is `paper-downloader`, pointing at the CLI module's `main`. The lockfile is committed.
- **Modules.** Four modules:
  - **parsing:** classifies a line and extracts the DOI plus fallback paper metadata.
  - **metadata:** Crossref lookup and the fallback chain.
  - **strategies:** one function per strategy, plus the shared download helper.
  - **cli:** argument handling, email resolution, the manifest, the failure log, and the per-paper waterfall.
- **Waterfall kept.** Each strategy stays its own function returning PDF bytes or nothing. The waterfall is now four steps: Unpaywall → Europe PMC → Semantic Scholar → direct DOI. Retry logic is not added inside strategies. Pacing stays at the per-paper level through `--delay`.
- **CLI entry point.** `main` accepts an optional argument list (`None` means read the process arguments). This is the single test seam.
- **Line classification.** After stripping whitespace and leading numbering, each line is one of: blank, comment (`#`), DOI line (the whole line is a DOI in one of the four accepted forms), citation line (a DOI URL appears within citation text), or skipped line. Trailing periods are stripped from DOIs. The DOI is normalised to its bare `10.…` form, and the DOI URL is always `https://doi.org/<doi>`.
- **Paper metadata.** Crossref `works/{doi}` is queried for every paper not skipped by the manifest, with `mailto` set to the email:
  - year: the first element of `issued.date-parts`
  - first author: the first author's `family` name, or else their `name` (consortium)
  - journal: the first `container-title`

  Any missing field falls back to the value parsed from the citation line, then to `0000` or `Unknown`. Folder naming keeps the existing sanitisation (journal reduced to alphanumerics).
- **DOI encoding.** Query-string values go through `requests`' `params`. DOIs inside URL paths (Unpaywall, Semantic Scholar, Crossref) are percent-encoded, with `/` left as is.
- **Direct DOI.** It returns PDF bytes or nothing, and applies the same acceptance rule as the shared download helper (status 200, more than 1 KB, PDF content type or `%PDF` magic). Landing-page HTML handling and the unused landing-page fetcher are removed.
- **Manifest.** A tab-separated file at the root of the output directory, with columns `doi`, `folder`, `strategy`, `date` (ISO date). It is read at start. Before any network call, a paper is skipped if its DOI is in the manifest and that row's PDF exists, unless `--force` is given. The suffix counter is seeded with folder names already in the manifest, so new names never collide. A row is appended right after each successful save. A forced re-download of a listed DOI replaces its row instead of adding a second one.
- **Failure log.** It is written at the root of the output directory only when there is at least one failure or skipped line. Each entry is a `# <reason>` line followed by the original line. Reasons are "no DOI found (line N)" and "PDF not found via any strategy". When a run has neither, any existing failure log is deleted. The file is itself a valid paper list.
- **Email resolution.** `--email`, then the `EMAIL` environment variable, then `EMAIL` in `.env` in the current directory. If none is set, the tool exits with an error. The User-Agent is built after the email is resolved. The email global stays mutable (per CLAUDE.md).
- **Defaults and help.** `--input List_of_papers.txt`, `--output papers`, `--delay 1.0`. New flag: `--force`. The description becomes "Download open-access PDFs for papers in a paper list."
- **Output.** After parsing, the tool prints the counts per line kind and a warning block for skipped lines. At the end it prints a summary of downloaded, already present and failed papers, with the failure log path when one was written.

## Testing Decisions

- **One seam.** Every test calls the CLI `main` with an argument list: a temporary paper list, a temporary output directory, `--delay 0` and `--email`. HTTP is faked at the `requests` transport layer with the `responses` library, with canned Crossref, Unpaywall, Europe PMC, Semantic Scholar and doi.org replies. No test touches the network, and unregistered URLs fail the test.
- **What a good test asserts.** Only externally visible results: which paper folders and PDF files exist (and their bytes), manifest rows, failure log contents, and console output for warnings and the summary. Tests never call internal helpers or assert on function names, so the internal modules can be refactored freely.
- **Behaviours covered:**
  - each accepted DOI-line form and its folder name from Crossref
  - citation and DOI lines for the same DOI giving one paper folder
  - Crossref missing or partial, falling back to citation values and then `Unknown`
  - consortium authors
  - titles or journals with periods
  - `_2` suffixes, including against folders from an earlier run's manifest
  - waterfall order (an earlier strategy hit means later strategies are never called)
  - a direct-DOI tiny or HTML body being rejected
  - DOIs with special characters producing correctly encoded requests
  - skip-existing making zero requests, re-download after PDF deletion, and `--force`
  - manifest rows appended and replaced
  - skipped-line warnings and failure log entries
  - re-running the failure log as input
  - deleting a stale failure log
  - email resolution order and the missing-email exit
- **Prior art.** None; the repo has no tests today. `tmp_path` and `responses` fixtures are the pattern to start from.
- **Manual check.** A live smoke test with a 4–5 line paper list mixing citation and DOI lines (run, re-run to confirm skipping, then re-run on the failure log) is done once before merge. It is not automated.

## Out of Scope

- Downloading supplementary files.
- A sixth strategy that reads the `citation_pdf_url` meta tag from landing pages.
- Replacing PubMed Central with the PMC Open Data bucket on AWS S3 (recorded as a rejected option in ADR 0001).
- Retry loops inside strategies, and concurrent downloads.
- Moving or renaming paper folders created by earlier runs under the old naming.
- Reading paper lists in formats other than plain text (BibTeX, RIS, CSV).
- Publishing the package to PyPI.

## Further Notes

- First, fast-forward `main` to `fix-email-handling` (the email fix), then implement this on a new branch.
- Crossref adds one request per paper not yet in the manifest. With the default `--delay 1.0`, a paper costs at least 2 seconds, or up to 5 when every strategy misses.
- No finding in the original handoff was checked against live APIs except PubMed Central. The other strategies' behaviour is assumed unchanged.
