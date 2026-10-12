# paper_downloader

Fetches open-access PDFs for a list of scientific papers, using only public APIs.

## Language

### Input

**Paper list**:
A text file with one paper per line. It may mix citation lines and DOI lines.
_Avoid_: Reference list, input list, citation file

**Citation line**:
A line holding a bibliographic citation that contains a DOI somewhere in it.
_Avoid_: Reference string, full reference

**DOI line**:
A line that holds only a DOI, as a `doi.org` URL, a `doi:` prefix, or a bare `10.…` identifier.
_Avoid_: DOI-only line, link line

**Skipped line**:
A non-blank, non-comment line in the paper list where no DOI could be found.
_Avoid_: Unparseable line, bad line

### Papers

**Paper**:
One published work, identified by its DOI.
_Avoid_: Article, publication, reference

**Paper metadata**:
A paper's year, first author's family name and journal. Crossref is the source of record; the citation text is a fallback.
_Avoid_: Citation info, bibliographic data

**Paper folder**:
The output folder for one paper, named `{year}_{FirstAuthor}_{Journal}` from its paper metadata.
_Avoid_: Paper directory, base name

### Downloading

**Strategy**:
One open-access source tried for a paper's PDF. Strategies are tried in a fixed order until one returns a PDF.
_Avoid_: Source, method, fallback

**Manifest**:
The record of every paper downloaded so far: its DOI, paper folder, the strategy that succeeded, and the date.
_Avoid_: Index, cache, download history

**Failure log**:
A paper list holding every line from the last run whose paper had no PDF found, or that was a skipped line, each with a comment giving the reason.
_Avoid_: Error log, failed list
