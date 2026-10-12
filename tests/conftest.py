"""Test harness: run the CLI against a temporary paper list with HTTP faked by `responses`."""

from pathlib import Path

import pytest
import responses

from paper_downloader import cli

@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Run every test in an empty working directory with no EMAIL from the shell."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMAIL", raising=False)


@pytest.fixture(autouse=True)
def http():
    """Fake HTTP for every test. A request to an unregistered URL fails the test.

    Strategies swallow exceptions, so the ConnectionError that `responses` raises for an
    unmatched request would be hidden. We check the recorded calls after the test instead.
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps
        unmatched = [c.request.url for c in rsps.calls if isinstance(c.response, Exception)]
        assert not unmatched, f"Unregistered URLs requested: {unmatched}"


@pytest.fixture
def run(tmp_path):
    """Write `lines` to a paper list and call main(argv). Returns the output directory."""

    def _run(lines: list[str], *extra: str, email: str | None = "test@example.com") -> Path:
        paper_list = tmp_path / "list.txt"
        paper_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output = tmp_path / "out"
        argv = ["--input", str(paper_list), "--output", str(output), "--delay", "0", *extra]
        if email is not None:
            argv += ["--email", email]
        cli.main(argv)
        return output

    return _run
