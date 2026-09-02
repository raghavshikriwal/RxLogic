"""
Typed domain exceptions for RxLogic.

Every failure mode in the reasoning pipeline raises one of these —
never a bare Exception — so the API layer can map errors to
specific, predictable HTTP responses instead of guessing.
"""


class RxLogicError(Exception):
    """Base class for all RxLogic domain exceptions."""


class UnknownMedicationError(RxLogicError):
    """Raised when a medication cannot be resolved against the knowledge base.

    Per the fail-safe design rule (Section 9): this must produce an
    explicit 'insufficient data' response, never a silent guess.
    """
    def __init__(self, medication_name: str):
        self.medication_name = medication_name
        super().__init__(f"Unknown medication: '{medication_name}' — insufficient data to reason about it.")


class InsufficientDataError(RxLogicError):
    """Raised when interaction/rule coverage is incomplete for a given case."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Insufficient data — consult a professional. Reason: {reason}")


class SchemaValidationError(RxLogicError):
    """Raised when LLM output fails validation against the structured schema.

    Enforces the strict schema boundary (Section 4.1): the LLM never
    talks to the reasoning engine directly with unvalidated data.
    """
    def __init__(self, raw_output: str, validation_errors: str):
        self.raw_output = raw_output
        self.validation_errors = validation_errors
        super().__init__(f"LLM output failed schema validation: {validation_errors}")


class ConstraintUnsatisfiableError(RxLogicError):
    """Raised when the CSP scheduler cannot find any feasible dose schedule."""
    def __init__(self, conflicting_constraints: list[str]):
        self.conflicting_constraints = conflicting_constraints
        super().__init__(
            f"No feasible schedule exists — conflicting constraints: {conflicting_constraints}"
        )


class ExternalAPIError(RxLogicError):
    """Raised when RxNav or openFDA calls fail (network, rate-limit, bad response)."""
    def __init__(self, api_name: str, status_code: int | None = None):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(f"{api_name} request failed (status: {status_code})")