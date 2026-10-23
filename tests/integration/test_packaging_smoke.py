"""Packaging smoke test verifying wheel integrity, entrypoints, and assets."""

import subprocess
import sys
import zipfile
from pathlib import Path


def test_wheel_artifact_contents() -> None:
    dist_dir = Path("dist")
    wheels = list(dist_dir.glob("eatdata-*.whl"))
    assert len(wheels) >= 1, "Wheel artifact not found in dist/. Run 'uv build' first."

    wheel_path = wheels[0]
    with zipfile.ZipFile(wheel_path) as z:
        names = set(z.namelist())

        # 1. Essential code modules
        assert "workbench/__init__.py" in names
        assert "workbench/cli/main.py" in names
        assert "workbench/domain/dataset.py" in names
        assert "workbench/engine/transformations.py" in names
        assert "workbench/adapters/storage/sqlite_repository.py" in names
        assert "workbench/adapters/ai/router.py" in names

        # 2. Offline UI static asset
        assert "workbench/ui/app.html" in names

        # 3. Entry point registration
        ep_entry = [n for n in names if n.endswith("entry_points.txt")]
        assert len(ep_entry) == 1
        ep_content = z.read(ep_entry[0]).decode("utf-8")
        assert "workbench = workbench.cli.main:main" in ep_content


def test_cli_help_smoke() -> None:
    """Verify workbench entrypoint executes cleanly via python -m."""
    result = subprocess.run(
        [sys.executable, "-m", "workbench.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "EatData" in result.stdout
    assert "profile" in result.stdout
    assert "pipeline" in result.stdout
    assert "transform" in result.stdout
    assert "export" in result.stdout
    assert "ui" in result.stdout
    assert "ai" in result.stdout
