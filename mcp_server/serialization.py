"""Compact MCP presentation; Python models keep their complete upstream payloads.

The include_raw opt-in follows slavb18/rzd-api b19e13b. See CREDITS.md.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any


def serialize(value: Any, *, include_raw: bool = False) -> Any:
    """Build a fresh JSON-compatible tree without copying excluded raw payloads."""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: serialize(getattr(value, item.name), include_raw=include_raw)
            for item in fields(value)
            if include_raw or item.name != "raw"
        }
    if isinstance(value, dict):
        return {
            key: serialize(item, include_raw=include_raw)
            for key, item in value.items()
            if include_raw or key != "raw"
        }
    if isinstance(value, (list, tuple)):
        return [serialize(item, include_raw=include_raw) for item in value]
    return value
