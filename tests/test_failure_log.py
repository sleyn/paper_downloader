"""Skipped lines are reported, and the failure log is a paper list that can be re-run."""

from fakes import crossref_missing, miss_everywhere, unpaywall_hit

FOUND = "10.1000/found"
MISSING = "10.1000/missing"
NO_DOI = "3. Smith J. A paper whose DOI I forgot to paste. Cell Reports. 2019. This line is quite long, more than eighty characters."


def test_skipped_line_reported_with_line_number_and_first_80_characters(run, http, capsys):
    crossref_missing(http, FOUND)
    unpaywall_hit(http, FOUND)

    run(["# reading list", FOUND, NO_DOI])

    console = capsys.readouterr().out
    assert f"line 3: {NO_DOI[:80]}" in console
    assert NO_DOI[80:] not in console


def test_failure_log_lists_reason_then_original_line(run, http):
    crossref_missing(http, FOUND)
    unpaywall_hit(http, FOUND)
    crossref_missing(http, MISSING)
    miss_everywhere(http)

    out = run([f"1. {FOUND}", f"2. doi:{MISSING}", NO_DOI])

    assert (out / "failed_downloads.txt").read_text() == (
        "# PDF not found via any strategy\n"
        f"2. doi:{MISSING}\n"
        "# no DOI found (line 3)\n"
        f"{NO_DOI}\n"
    )


def test_failure_log_as_input_retries_exactly_the_failed_papers(run, http, tmp_path):
    crossref_missing(http, FOUND)
    unpaywall_hit(http, FOUND)
    crossref_missing(http, MISSING)
    miss_everywhere(http)
    out = run([FOUND, MISSING])
    first_run_calls = len(http.calls)

    run([], "--input", str(out / "failed_downloads.txt"))

    retried = [c.request.url for c in http.calls[first_run_calls:]]
    assert retried[0] == f"https://api.crossref.org/works/{MISSING}?mailto=test%40example.com"
    assert not any(FOUND in url for url in retried)


def test_clean_run_deletes_an_old_failure_log(run, http, tmp_path):
    old_log = tmp_path / "out" / "failed_downloads.txt"
    old_log.parent.mkdir()
    old_log.write_text("# PDF not found via any strategy\n10.1000/old\n")
    crossref_missing(http, FOUND)
    unpaywall_hit(http, FOUND)

    run([FOUND])

    assert not old_log.exists()
