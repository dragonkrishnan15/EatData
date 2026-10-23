"""Security and privacy tests for AI consent gates and payload boundaries.

Invariants:
- STRICT PRIVACY (Rules 2, 6, 8, 9): Zero raw dataset rows transmitted to AI providers.
- External or AI transmissions strictly blocked without prior explicit consent.
- Payloads are hashed with SHA-256; tampering or altering payload invalidates consent.
"""

import pytest

from workbench.adapters.ai.metadata import MetadataPackageBuilder
from workbench.adapters.ai.router import AIRouter
from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import ConsentRequiredError
from workbench.engine.profiler import Profiler


@pytest.fixture
def test_dataset():
    cols = [
        ColumnMetadata(name="ssn", data_type=DataType.STRING),
        ColumnMetadata(name="salary", data_type=DataType.FLOAT),
    ]
    rows = [
        ("000-12-3456", 85000.0),
        ("000-98-7654", 92000.0),
    ]
    return Dataset(name="payroll", columns=cols, rows=rows)


def test_consent_gate_enforcement(test_dataset: Dataset) -> None:
    profile = Profiler().profile(test_dataset)
    builder = MetadataPackageBuilder()
    package = builder.build(profile, alias_columns=True)

    router = AIRouter()

    # 1. Calling request_recipe without explicit consent MUST raise ConsentRequiredError
    with pytest.raises(ConsentRequiredError, match="User consent required"):
        router.request_recipe("mock", package, "clean ssn column", explicit_consent=False)

    # 2. Providing explicit_consent=True records consent and succeeds
    pipeline = router.request_recipe(
        "mock", package, "trim whitespace and clean ssn column", explicit_consent=True
    )
    assert pipeline is not None
    assert len(pipeline.steps) > 0

    # 3. Subsequent call for the same package succeeds without re-prompting
    pipeline2 = router.request_recipe(
        "mock", package, "trim whitespace and clean ssn column", explicit_consent=False
    )
    assert pipeline2 is not None

    # 4. Altering the dataset or metadata produces a new payload hash requiring new consent
    modified_cols = [ColumnMetadata(name="new_col", data_type=DataType.STRING)]
    modified_ds = Dataset(name="payroll_mod", columns=modified_cols, rows=[("a",)])
    new_profile = Profiler().profile(modified_ds)
    new_package = builder.build(new_profile, alias_columns=True)

    with pytest.raises(ConsentRequiredError, match="User consent required"):
        router.request_recipe("mock", new_package, "clean data", explicit_consent=False)


def test_zero_raw_rows_in_metadata_package(test_dataset: Dataset) -> None:
    profile = Profiler().profile(test_dataset)
    builder = MetadataPackageBuilder()
    package = builder.build(profile, alias_columns=False)

    json_str = package.payload_json

    # Assert that raw SSN values and salary values never exist in the payload
    assert "000-12-3456" not in json_str
    assert "000-98-7654" not in json_str
    assert "85000" not in json_str
    assert "92000" not in json_str
    assert "rows" not in package.payload_dict
