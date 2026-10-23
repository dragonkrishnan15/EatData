"""Unit tests for curated domain cleaning templates."""

import json
from pathlib import Path

import pytest

from workbench.adapters.importers.csv_importer import CsvImporter
from workbench.cli.main import main
from workbench.engine.registry import TransformationRegistry
from workbench.templates.catalog import TemplateCatalog


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parents[2] / "fixtures"


def test_template_catalog_builtins() -> None:
    catalog = TemplateCatalog()
    templates = catalog.list_templates()
    assert len(templates) >= 4

    ids = {t.template_id for t in templates}
    assert "crm_standardize" in ids
    assert "financial_clean" in ids
    assert "clinical_clean" in ids
    assert "ecommerce_catalog" in ids


def test_template_catalog_get_and_to_dict() -> None:
    catalog = TemplateCatalog()
    tpl = catalog.get("crm_standardize")
    assert tpl is not None
    assert tpl.template_id == "crm_standardize"
    assert tpl.category == "Sales & CRM"

    d = tpl.to_dict()
    assert d["template_id"] == "crm_standardize"
    assert "pipeline" in d
    assert len(d["pipeline"]["steps"]) == 3


def test_template_apply_execution(fixtures_dir: Path) -> None:
    messy_csv = fixtures_dir / "messy_sample.csv"
    importer = CsvImporter()
    dataset = importer.import_file(messy_csv).dataset

    catalog = TemplateCatalog()
    tpl = catalog.get("crm_standardize")
    assert tpl is not None

    registry = TransformationRegistry()
    transformed, _ = registry.execute_pipeline(dataset, tpl.pipeline)

    # Duplicates dropped
    assert transformed.row_count <= dataset.row_count
    # Headers normalized to snake_case
    for col in transformed.column_names:
        assert " " not in col
        assert col == col.lower()


def test_template_unknown() -> None:
    catalog = TemplateCatalog()
    assert catalog.get("non_existent_template") is None


def test_cli_template_list(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["template", "list", "--format", "json"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, list)
    assert len(data) >= 4


def test_cli_template_apply(fixtures_dir: Path, tmp_path: Path) -> None:
    input_file = fixtures_dir / "messy_sample.csv"
    output_file = tmp_path / "cleaned_output.csv"

    code = main(
        [
            "template",
            "apply",
            "crm_standardize",
            str(input_file),
            "--output",
            str(output_file),
        ]
    )
    assert code == 0
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_cli_template_apply_unknown_error(
    fixtures_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_file = fixtures_dir / "messy_sample.csv"
    output_file = tmp_path / "out.csv"

    code = main(
        [
            "template",
            "apply",
            "invalid_template_id",
            str(input_file),
            "--output",
            str(output_file),
        ]
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "Unknown template" in err
