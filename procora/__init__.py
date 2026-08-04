"""Procora: one Python API for stored procedures across databases."""

from importlib.metadata import PackageNotFoundError, version

from .backend import Backend, ConnectionDiscarder, ConnectionFactory, ConnectionReleaser
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
from .models import BackendCapabilities, ParameterMode, ProcedureInfo, ProcedureParameter
from .protocols import ConnectionProtocol, CursorProtocol
from .result import ProcedureResult, ResultSet

__all__ = [
    "AmbiguousProcedureError",
    "Backend",
    "BackendCapabilities",
    "ConfigurationError",
    "CleanupErrorHandler",
    "ConnectionFactory",
    "ConnectionDiscarder",
    "ConnectionProtocol",
    "ConnectionReleaser",
    "CursorProtocol",
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

try:
    __version__ = version("procora")
except PackageNotFoundError:  # Source tree used without installation.
    __version__ = "0+unknown"
