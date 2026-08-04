"""Portable stored-procedure responses."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .models import ProcedureInfo


@dataclass(frozen=True, slots=True)
class ResultSet:
    """One tabular result set."""

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]

    def as_list(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.rows]


@dataclass(frozen=True, slots=True)
class ProcedureResult:
    """All portable values returned by one procedure call."""

    procedure: ProcedureInfo
    result_sets: tuple[ResultSet, ...] = ()
    output: dict[str, Any] = field(default_factory=dict)
    return_value: int | None = None

    @property
    def rows(self) -> list[dict[str, Any]]:
        return self.result_sets[0].as_list() if self.result_sets else []

    @property
    def first(self) -> dict[str, Any] | None:
        if not self.result_sets:
            return None
        rows = self.result_sets[0].rows
        return dict(rows[0]) if rows else None

    @property
    def scalar(self) -> Any:
        if not self.result_sets or not self.result_sets[0].rows:
            return None
        return next(iter(self.result_sets[0].rows[0].values()), None)

    def json(self) -> Any:
        """Decode JSON from the first scalar value."""
        value = self.scalar
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            raise TypeError("The first procedure value is not JSON text")
        return json.loads(value)
