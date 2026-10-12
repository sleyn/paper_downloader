"""Email resolution: --email, then the EMAIL environment variable, then .env in the current directory."""

from urllib.parse import parse_qs, urlparse

import pytest
from conftest import FAKE_PDF

DOI_CITATION = "Leyn SA. Things. Nature Communications. 2024. https://doi.org/10.1038/s41467-024-12345-6"


@pytest.fixture
def unpaywall_hit(http):
    http.get(
        "https://api.unpaywall.org/v2/10.1038/s41467-024-12345-6",
        json={"best_oa_location": {"url_for_pdf": "https://oa.example.org/paper.pdf"}},
    )
    http.get("https://oa.example.org/paper.pdf", body=FAKE_PDF, content_type="application/pdf")
    return http


def email_sent_to_unpaywall(http) -> str:
    url = http.calls[0].request.url
    assert url.startswith("https://api.unpaywall.org/")
    return parse_qs(urlparse(url).query)["email"][0]


def test_email_flag_overrides_environment_and_dotenv(run, unpaywall_hit, tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL", "env@example.com")
    (tmp_path / ".env").write_text("EMAIL=dotenv@example.com\n")

    run([DOI_CITATION], email="flag@example.com")

    assert email_sent_to_unpaywall(unpaywall_hit) == "flag@example.com"


def test_environment_variable_overrides_dotenv(run, unpaywall_hit, tmp_path, monkeypatch):
    monkeypatch.setenv("EMAIL", "env@example.com")
    (tmp_path / ".env").write_text("EMAIL=dotenv@example.com\n")

    run([DOI_CITATION], email=None)

    assert email_sent_to_unpaywall(unpaywall_hit) == "env@example.com"


def test_dotenv_in_current_directory_is_used(run, unpaywall_hit, tmp_path):
    (tmp_path / ".env").write_text("EMAIL=dotenv@example.com\n")

    run([DOI_CITATION], email=None)

    assert email_sent_to_unpaywall(unpaywall_hit) == "dotenv@example.com"


def test_no_email_exits_with_error(run, http):
    with pytest.raises(SystemExit) as exc:
        run([DOI_CITATION], email=None)

    assert "Email address is required" in str(exc.value.code)
    assert len(http.calls) == 0
