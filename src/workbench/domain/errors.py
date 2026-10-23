"""Structured error hierarchy for the EatData workbench.

Invariants:
- Error messages presented to users must be safe and actionable.
- Error representations (__repr__, __str__) must never expose raw data rows, cell values,
  or unredacted secrets.
"""

from typing import Any


class WorkbenchError(Exception):
    """Base exception for all workbench errors."""

    def __init__(
        self,
        message: str,
        code: str = "WORKBENCH_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    @property
    def user_message(self) -> str:
        """User-safe actionable message without sensitive context."""
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert error to a structured dictionary."""
        return {
            "code": self.code,
            "message": self.user_message,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class UnsupportedFormatError(WorkbenchError):
    """Raised when an unrecognized or unsupported file format is encountered."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="UNSUPPORTED_FORMAT", details=details)


class ParseFailureError(WorkbenchError):
    """Raised when parsing of a file or record fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PARSE_FAILURE", details=details)


class ValidationError(WorkbenchError):
    """Raised when input, parameter, schema, or column validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class ResourceLimitError(WorkbenchError):
    """Raised when file size, row count, column count, or memory limits are exceeded."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="RESOURCE_LIMIT_EXCEEDED", details=details)


class ProviderUnavailableError(WorkbenchError):
    """Raised when an external or local AI provider endpoint is unreachable or disabled."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PROVIDER_UNAVAILABLE", details=details)


class ConsentRequiredError(WorkbenchError):
    """Raised when an operation requiring user consent is attempted without prior consent."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="CONSENT_REQUIRED", details=details)


class InvalidRecipeError(WorkbenchError):
    """Raised when an AI proposed recipe violates allowlist schemas, parameters, or bounds."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="INVALID_RECIPE", details=details)


class ExecutionFailureError(WorkbenchError):
    """Raised when a transformation step fails during pipeline execution."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="EXECUTION_FAILURE", details=details)


class ExportConflictError(WorkbenchError):
    """Raised when an export destination already exists without overwrite approval."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="EXPORT_CONFLICT", details=details)


class StorageFailureError(WorkbenchError):
    """Raised when local database or settings persistence fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="STORAGE_FAILURE", details=details)


class CancellationError(WorkbenchError):
    """Raised when a long-running operation is safely cancelled by the user."""

    def __init__(
        self,
        message: str = "Operation cancelled by user.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="CANCELLED", details=details)
