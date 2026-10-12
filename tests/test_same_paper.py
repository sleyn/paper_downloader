"""One paper, one paper folder: however and however often it is listed."""

from fakes import crossref_missing, crossref_record, miss_everywhere, unpaywall_hit


def folders(out) -> list[str]:
    return sorted(p.name for p in out.iterdir() if p.is_dir())


def test_doi_case_does_not_make_a_second_paper(run, http):
    crossref_record(http, "10.1038/nmeth.1923", year=2012, family="Langmead", journal="Nature Methods")
    unpaywall_hit(http, "10.1038/nmeth.1923")
    out = run(["10.1038/NMETH.1923"])
    calls = len(http.calls)

    run(["doi:10.1038/nmeth.1923"])

    assert folders(out) == ["2012_Langmead_NatureMethods"]
    assert len(http.calls) == calls


def test_doi_listed_twice_in_one_run_is_tried_once(run, http, capsys):
    crossref_missing(http, "10.1000/missing")
    miss_everywhere(http)

    out = run(["10.1000/missing", "https://doi.org/10.1000/missing"])

    crossref_calls = [c for c in http.calls if "crossref" in c.request.url]
    assert len(crossref_calls) == 1
    assert folders(out) == []


def test_punctuation_after_a_citation_doi_is_not_part_of_it(run, http):
    doi = "10.1000/abc"
    crossref_missing(http, doi)
    unpaywall_hit(http, doi)

    run([f"Smith J. Things. Cell. 2019. (https://doi.org/{doi}), Abstract"])

    assert http.calls[0].request.url.startswith(f"https://api.crossref.org/works/{doi}?")


def test_doi_with_balanced_parentheses_is_kept_whole(run, http):
    doi = "10.1002/(sici)1097-4636(199601)30:1<1::aid-jbm1>3.0.co;2-q"
    crossref_missing(http, doi)
    miss_everywhere(http)

    run([doi])

    assert http.calls[0].request.url.startswith(
        "https://api.crossref.org/works/10.1002/%28sici%291097-4636%28199601%2930%3A1%3C1%3A%3Aaid-jbm1%3E3.0.co%3B2-q?"
    )


def test_folder_left_by_a_run_before_the_manifest_is_not_overwritten(run, http, tmp_path):
    old = tmp_path / "out" / "2024_Leyn_NatureCommunications"
    old.mkdir(parents=True)
    (old / "2024_Leyn_NatureCommunications.pdf").write_bytes(b"older paper")
    doi = "10.1038/s41467-024-12345-6"
    crossref_record(http, doi, year=2024, family="Leyn", journal="Nature Communications")
    unpaywall_hit(http, doi)

    out = run([doi])

    assert (old / "2024_Leyn_NatureCommunications.pdf").read_bytes() == b"older paper"
    assert folders(out) == ["2024_Leyn_NatureCommunications", "2024_Leyn_NatureCommunications_2"]
