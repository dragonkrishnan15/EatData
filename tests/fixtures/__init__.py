"""Synthetic test fixtures package and path helper."""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def get_fixture_path(filename: str) -> Path:
    """Return the absolute path to a fixture file."""
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Fixture '{filename}' not found at {path}")
    return path
