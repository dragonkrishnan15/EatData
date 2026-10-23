"""Domain models and core contracts for the EatData workbench."""

from workbench.domain.dataset import ColumnMetadata, Dataset, DataType
from workbench.domain.errors import (
    CancellationError,
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
from workbench.domain.operations import ALLOWLISTED_OPERATIONS, Operation, OperationName
from workbench.domain.pipeline import Pipeline
from workbench.domain.profile import ColumnProfile, DatasetProfile

__all__ = [
    "ALLOWLISTED_OPERATIONS",
    "CancellationError",
    "ColumnMetadata",
    "ColumnProfile",
    "ConsentRequiredError",
    "DataType",
    "Dataset",
    "DatasetProfile",
    "ExecutionFailureError",
    "ExportConflictError",
    "InvalidRecipeError",
    "Operation",
    "OperationName",
    "ParseFailureError",
    "Pipeline",
    "ProviderUnavailableError",
    "ResourceLimitError",
    "StorageFailureError",
    "UnsupportedFormatError",
    "ValidationError",
    "WorkbenchError",
]
