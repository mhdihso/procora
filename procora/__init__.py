"""Procora: one Python API for stored procedures across databases."""

from .backend import Backend, ConnectionFactory, ConnectionReleaser
from .database import CleanupErrorHandler, Database, Procedure
from .errors import (
    AmbiguousProcedureError,
    ConfigurationError,
    DatabaseConnectionError,
    DriverNotInstalledError,
    ProcedureDiscoveryError,
    ProcedureExecutionError,
    ProcedureNotFoundError,
    ProcedureParameterError,
    ProcoraError,
    UnsupportedParameterError,
)
from .factory import connect, get_backend
from .models import ParameterMode, ProcedureInfo, ProcedureParameter
from .result import ProcedureResult, ResultSet

__all__ = [
    "AmbiguousProcedureError",
    "Backend",
    "ConfigurationError",
    "CleanupErrorHandler",
    "ConnectionFactory",
    "ConnectionReleaser",
    "Database",
    "DatabaseConnectionError",
    "DriverNotInstalledError",
    "ParameterMode",
    "Procedure",
    "ProcedureDiscoveryError",
    "ProcedureExecutionError",
    "ProcedureInfo",
    "ProcedureNotFoundError",
    "ProcedureParameter",
    "ProcedureParameterError",
    "ProcedureResult",
    "ProcoraError",
    "ResultSet",
    "UnsupportedParameterError",
    "connect",
    "get_backend",
]

__version__ = "1.0.0"
