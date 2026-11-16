"""Typed accessors for asyncpg records, whose column values are untyped (``Any``)."""

from datetime import datetime
from typing import cast
from uuid import UUID

from asyncpg import Record


def _value(row: Record, key: str) -> object:
    return cast(object, row[key])


def record_dict(row: Record) -> dict[str, object]:
    """Column name to value, for ``Model.model_validate``."""
    return dict(row.items())


def require_row(row: Record | None, what: str) -> Record:
    """A row the statement must return (``RETURNING`` or an upsert)."""
    if row is None:
        raise RuntimeError(f"{what} returned no row")
    return row


def col_int(row: Record, key: str) -> int:
    value = _value(row, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"column {key!r} is not an integer: {value!r}")
    return value


def col_str(row: Record, key: str) -> str:
    value = _value(row, key)
    if not isinstance(value, str):
        raise TypeError(f"column {key!r} is not text: {value!r}")
    return value


def col_opt_str(row: Record, key: str) -> str | None:
    value = _value(row, key)
    return None if value is None else col_str(row, key)


def col_uuid(row: Record, key: str) -> UUID:
    value = _value(row, key)
    if not isinstance(value, UUID):
        raise TypeError(f"column {key!r} is not a UUID: {value!r}")
    return value


def col_datetime(row: Record, key: str) -> datetime:
    value = col_opt_datetime(row, key)
    if value is None:
        raise TypeError(f"column {key!r} is NULL")
    return value


def col_opt_datetime(row: Record, key: str) -> datetime | None:
    value = _value(row, key)
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise TypeError(f"column {key!r} is not a timestamp: {value!r}")
    return value
