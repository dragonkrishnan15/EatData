"""Unit tests for the structured error hierarchy."""

from workbench.domain.errors import (
    ConsentRequiredError,
    ExecutionFailureError,
    ExportConflictError,
    InvalidRecipeError,
    ParseFailureError,
    ProviderUnavailableError,
    ResourceLimitError,
    StorageFailureError,
    UnsupportedFormatError,
    ValidationError,
    WorkbenchError,
)


def test_structured_error_properties() -> None:
    err = ValidationError("Column 'age' must be numeric.", details={"column": "age"})
    assert isinstance(err, WorkbenchError)
    assert isinstance(err, Exception)
    assert err.code == "VALIDATION_ERROR"
    assert err.user_message == "Column 'age' must be numeric."
    assert err.details == {"column": "age"}

    err_dict = err.to_dict()
    assert err_dict == {
        "code": "VALIDATION_ERROR",
        "message": "Column 'age' must be numeric.",
        "details": {"column": "age"},
    }
    assert "[VALIDATION_ERROR]" in str(err)


def test_error_classes_inherit_from_workbench_error() -> None:
    error_classes = [
        UnsupportedFormatError,
        ParseFailureError,
        ValidationError,
        ResourceLimitError,
        ProviderUnavailableError,
        ConsentRequiredError,
        InvalidRecipeError,
        ExecutionFailureError,
        ExportConflictError,
        StorageFailureError,
    ]
    for cls in error_classes:
        instance = cls("Test error")
        assert isinstance(instance, WorkbenchError)
        assert instance.code != "WORKBENCH_ERROR"
