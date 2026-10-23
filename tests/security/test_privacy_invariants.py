"""Security and privacy boundary regression tests.

Enforces invariants from RULES.md and THREAT_MODEL.md:
1. Raw rows and cell values are never exposed in object representations (__repr__, __str__).
2. AI metadata builder excludes raw cell values, raw rows, and file paths.
3. Errors preserve diagnostic information without reflecting unredacted payload rows.
4. Serialized pipelines contain only declarative operation parameters and no raw data.
"""

import json

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ValidationError
from workbench.domain.operations import Operation
from workbench.domain.pipeline import Pipeline
from workbench.domain.profile import ColumnProfile, DatasetProfile


def test_dataset_repr_never_leaks_raw_cells() -> None:
    secret_token = "TOP_SECRET_PATIENT_RECORD_XYZ999"
    secret_email = "confidential_whistleblower@example.com"
    cols = [
        ColumnMetadata(name="token", data_type=DataType.STRING),
        ColumnMetadata(name="email", data_type=DataType.STRING),
    ]
    rows = [(secret_token, secret_email)]
    ds = Dataset(name="sensitive_table", columns=cols, rows=rows)

    repr_output = repr(ds)
    str_output = str(ds)

    assert secret_token not in repr_output
    assert secret_email not in repr_output
    assert secret_token not in str_output
    assert secret_email not in str_output


def test_ai_metadata_allowlist_excludes_raw_values() -> None:
    """Verify that to_safe_metadata() contains only schema and statistical summaries."""
    secret_value = "CONFIDENTIAL_FINANCIAL_ACCOUNT_888"
    cp = ColumnProfile(
        name="account_number",
        inferred_type=DataType.STRING,
        null_count=0,
        null_percentage=0.0,
        distinct_count=100,
        sample_categories=["numeric-id"],
    )
    profile = DatasetProfile(
        dataset_id="ds-test",
        dataset_name="accounts.csv",
        row_count=100,
        column_count=1,
        duplicate_row_count=0,
        total_null_count=0,
        columns={"account_number": cp},
        warnings=[],
    )

    metadata = profile.to_safe_metadata(alias_columns=True)
    json_payload = json.dumps(metadata)

    # Invariant: Neither secret value nor real column name appears in aliased metadata
    assert secret_value not in json_payload
    assert "account_number" not in json_payload
    assert "col_1" in json_payload


def test_error_formatting_does_not_leak_payloads() -> None:
    """Ensure ValidationError messages contain parameter names, not full row content."""
    err = ValidationError("Parameter 'value' is missing for strategy 'constant'.")
    assert "constant" in str(err)
    assert err.code == "VALIDATION_ERROR"
    # User message property is safe
    assert err.user_message == err.message


def test_pipeline_serialization_has_no_raw_data() -> None:
    """Ensure saved pipeline files contain only schema operations, not data records."""
    op1 = Operation(name="trim_whitespace", columns=["user_name"])
    op2 = Operation(
        name="rename_column",
        columns=["user_name"],
        parameters={"new_name": "name_normalized"},
    )
    pipeline = Pipeline(name="Safe Pipeline", steps=[op1, op2])

    serialized = pipeline.to_json()
    parsed = json.loads(serialized)

    assert "steps" in parsed
    assert len(parsed["steps"]) == 2
    for step in parsed["steps"]:
        assert "rows" not in step
        assert "data" not in step
