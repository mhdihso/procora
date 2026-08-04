"""Database-neutral procedure metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class BackendCapabilities:
    """Portable behavior advertised by a backend."""

    supports_multiple_result_sets: bool = False
    supports_output_parameters: bool = False
    supports_return_value: bool = False
    supports_overloads: bool = False
    timeout_kind: Literal["statement", "driver", "socket", "unsupported"] = "unsupported"
    supports_per_borrow_timeout: bool = True
    metadata_defaults_are_reliable: bool = False
    buffers_results: bool = True


class ParameterMode(str, Enum):
    IN = "IN"
    OUT = "OUT"
    INOUT = "INOUT"

    @property
    def accepts_input(self) -> bool:
        return self in {ParameterMode.IN, ParameterMode.INOUT}

    @property
    def returns_output(self) -> bool:
        return self in {ParameterMode.OUT, ParameterMode.INOUT}


@dataclass(frozen=True, slots=True)
class ProcedureParameter:
    """One procedure parameter discovered from a database catalog."""

    position: int
    name: str
    native_type: str
    mode: ParameterMode = ParameterMode.IN
    has_default: bool = False
    backend_data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_data", MappingProxyType(dict(self.backend_data)))

    @property
    def python_name(self) -> str:
        value = self.name.removeprefix("@")
        return value or f"arg_{self.position}"


@dataclass(frozen=True, slots=True)
class ProcedureInfo:
    """Stored-procedure metadata resolved by a backend."""

    backend: str
    schema: str
    name: str
    parameters: tuple[ProcedureParameter, ...] = ()
    identity: str | int | None = None
    backend_data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend_data", MappingProxyType(dict(self.backend_data)))

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    @property
    def input_parameters(self) -> tuple[ProcedureParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.mode.accepts_input)

    @property
    def output_parameters(self) -> tuple[ProcedureParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.mode.returns_output)
