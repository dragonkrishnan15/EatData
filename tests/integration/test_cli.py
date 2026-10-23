"""CLI integration tests."""

import json
from pathlib import Path

from tests.fixtures import get_fixture_path
from workbench.cli.main import main


def test_cli_profile_table(capsys) -> None:
    path = str(get_fixture_path("clean_sample.csv"))
    exit_code = main(["profile", path])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Dataset Profile: clean_sample" in captured.out
    assert "Rows:               5" in captured.out
    assert "Columns:            6" in captured.out


def test_cli_profile_json(capsys) -> None:
    path = str(get_fixture_path("clean_sample.csv"))
    exit_code = main(["profile", path, "--format", "json"])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["row_count"] == 5
    assert data["column_count"] == 6


def test_cli_pipeline_validate(tmp_path: Path, capsys) -> None:
    pipe_file = tmp_path / "pipe.json"
    pipe_file.write_text(
        json.dumps(
            {
                "name": "CLI Pipeline",
                "steps": [{"name": "trim_whitespace"}],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["pipeline", "validate", str(pipe_file)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Pipeline 'CLI Pipeline' (version 1.0) is valid." in captured.out


def test_cli_transform(tmp_path: Path, capsys) -> None:
    in_path = str(get_fixture_path("messy_sample.csv"))
    out_file = tmp_path / "cleaned.csv"
    pipe_file = tmp_path / "pipe.json"

    pipe_file.write_text(
        json.dumps(
            {
                "name": "Clean Pipeline",
                "steps": [
                    {"name": "trim_whitespace"},
                    {"name": "drop_duplicates"},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "transform",
            in_path,
            "--pipeline",
            str(pipe_file),
            "--output",
            str(out_file),
        ]
    )

    assert exit_code == 0
    assert out_file.exists()
    captured = capsys.readouterr()
    assert "Successfully transformed dataset" in captured.out
    assert "drop_duplicates: 1 rows affected" in captured.out


def test_cli_export(tmp_path: Path, capsys) -> None:
    in_path = str(get_fixture_path("clean_sample.csv"))
    out_file = tmp_path / "converted.json"

    exit_code = main(["export", in_path, "--output", str(out_file)])
    assert exit_code == 0
    assert out_file.exists()
    captured = capsys.readouterr()
    assert "Exported 5 rows to" in captured.out


def test_cli_overwrite_conflict(tmp_path: Path, capsys) -> None:
    in_path = str(get_fixture_path("clean_sample.csv"))
    existing_file = tmp_path / "existing.csv"
    existing_file.write_text("dummy", encoding="utf-8")

    # Without --overwrite -> fails with code 1
    exit_code = main(["export", in_path, "--output", str(existing_file)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Workbench Error: Destination file already exists" in captured.err

    # With --overwrite -> succeeds with code 0
    exit_code_ok = main(["export", in_path, "--output", str(existing_file), "--overwrite"])
    assert exit_code_ok == 0


def test_cli_pipeline_save_and_list(tmp_path: Path, capsys) -> None:
    pipe_file = tmp_path / "saved_pipe.json"
    pipe_file.write_text(
        json.dumps(
            {
                "id": "cli-pipe-99",
                "name": "Integration Pipeline",
                "version": "1.0",
                "steps": [{"name": "trim_whitespace"}],
            }
        ),
        encoding="utf-8",
    )

    # Save pipeline
    exit_code = main(["pipeline", "save", str(pipe_file), "--description", "Test desc"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Saved pipeline 'Integration Pipeline'" in captured.out

    # List pipelines
    exit_list = main(["pipeline", "list"])
    assert exit_list == 0
    captured_list = capsys.readouterr()
    assert "Integration Pipeline" in captured_list.out


def test_cli_history_list_and_purge(capsys) -> None:
    # History list
    exit_code = main(["history", "list", "--limit", "10"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Execution History" in captured.out or "No execution history records" in captured.out

    # History purge
    exit_purge = main(["history", "purge"])
    assert exit_purge == 0
    captured_purge = capsys.readouterr()
    assert "Purged" in captured_purge.out


def test_cli_ai_propose_workflow(tmp_path: Path, capsys) -> None:
    in_path = str(get_fixture_path("clean_sample.csv"))
    out_pipe = tmp_path / "proposed.json"

    # 1. Preview payload without consent returns code 0 and displays payload
    code_preview = main(
        [
            "ai",
            "propose",
            in_path,
            "--prompt",
            "clean whitespace",
            "--preview-payload",
        ]
    )
    assert code_preview == 0
    cap_prev = capsys.readouterr()
    assert "Outgoing AI Metadata Payload Preview" in cap_prev.out
    assert "Payload SHA-256" in cap_prev.out

    # 2. Calling without consent or preview fails with code 1
    code_no_consent = main(
        [
            "ai",
            "propose",
            in_path,
            "--prompt",
            "clean whitespace",
        ]
    )
    assert code_no_consent == 1
    cap_err = capsys.readouterr()
    assert "Consent required" in cap_err.err

    # 3. Calling with --consent and --alias-columns succeeds and writes pipeline JSON
    code_ok = main(
        [
            "ai",
            "propose",
            in_path,
            "--prompt",
            "trim whitespace and drop duplicates",
            "--consent",
            "--alias-columns",
            "--output-pipeline",
            str(out_pipe),
        ]
    )
    assert code_ok == 0
    cap_ok = capsys.readouterr()
    assert "AI Proposed Recipe" in cap_ok.out
    assert out_pipe.exists()
    assert "trim_whitespace" in out_pipe.read_text(encoding="utf-8")
