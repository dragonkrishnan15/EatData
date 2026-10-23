"""Baseline environment and package smoke tests."""

import workbench


def test_package_version() -> None:
    """Verify package version is defined and semantic."""
    assert workbench.__version__ == "0.1.0"
