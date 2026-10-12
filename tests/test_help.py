"""The help text describes only what the tool does."""

import pytest

from paper_downloader import cli


def test_help_describes_paper_list_without_supplementary_files(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    help_text = capsys.readouterr().out
    assert "Download open-access PDFs for papers in a paper list." in help_text
    assert "supplementary" not in help_text.lower()
