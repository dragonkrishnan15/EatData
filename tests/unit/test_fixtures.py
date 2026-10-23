"""Unit tests verifying synthetic test fixtures."""

from tests.fixtures import get_fixture_path


def test_fixtures_exist() -> None:
    expected_files = [
        "clean_sample.csv",
        "messy_sample.csv",
        "malformed.csv",
        "empty.csv",
        "header_only.csv",
        "formula_injection.csv",
        "clean_sample.json",
        "nested_sample.json",
        "malformed.json",
    ]
    for filename in expected_files:
        path = get_fixture_path(filename)
        assert path.exists()


def test_fixtures_no_sensitive_or_credential_data() -> None:
    """Verify that fixtures contain no secrets or real customer sensitive records."""
    banned_substrings = [
        "sk-proj-",
        "AIzaSy",
        "ghp_",
        "AKIA",
        "BEGIN RSA PRIVATE KEY",
        "password=",
        "secret_key",
    ]
    expected_files = [
        "clean_sample.csv",
        "messy_sample.csv",
        "malformed.csv",
        "formula_injection.csv",
        "clean_sample.json",
        "nested_sample.json",
    ]
    for filename in expected_files:
        content = get_fixture_path(filename).read_text(encoding="utf-8")
        for banned in banned_substrings:
            assert banned not in content
