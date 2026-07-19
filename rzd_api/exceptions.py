from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import Station


class RzdError(Exception):
    """Base exception for the package."""


class RzdValidationError(RzdError):
    """Raised when a public API argument is invalid."""


class RzdTransportError(RzdError):
    """Raised when an HTTP request could not be completed."""


class RzdHTTPError(RzdTransportError):
    """Raised for a non-success HTTP response."""

    def __init__(self, status_code: int, body_preview: str = "") -> None:
        self.status_code = status_code
        self.body_preview = body_preview
        detail = f": {body_preview}" if body_preview else ""
        super().__init__(f"RZD HTTP error {status_code}{detail}")


class RzdAPIError(RzdError):
    """Raised when the RZD API reports an application-level error."""

    def __init__(self, code: Any = None, message: str = "RZD API returned an error.") -> None:
        self.code = code
        self.message = message
        prefix = f"RZD API error {code}" if code is not None else "RZD API error"
        super().__init__(f"{prefix}: {message}")


class RzdSchemaError(RzdError):
    """Raised when an endpoint response no longer matches the supported schema."""


class RzdStationNotFoundError(RzdValidationError):
    """Raised when no station matches the requested name."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f"Station not found: {query}")


class RzdAmbiguousStationError(RzdValidationError):
    """Raised when a station name resolves to more than one candidate."""

    def __init__(self, query: str, candidates: list[Station]) -> None:
        self.query = query
        self.candidates = candidates
        rendered = ", ".join(f"{item.name} ({item.code})" for item in candidates)
        super().__init__(f"Ambiguous station '{query}': {rendered}")
