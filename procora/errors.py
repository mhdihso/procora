"""Public exception hierarchy."""


class ProcoraError(Exception):
    """Base class for expected Procora errors."""


class ConfigurationError(ProcoraError, ValueError):
    """Backend or connection configuration is invalid."""


class DriverNotInstalledError(ConfigurationError, ImportError):
    """The optional driver for a selected backend is not installed."""


class DatabaseConnectionError(ProcoraError):
    """A database connection could not be created or checked."""


class ProcedureNotFoundError(ProcoraError, LookupError):
    """The requested stored procedure does not exist."""


class AmbiguousProcedureError(ProcoraError, LookupError):
    """More than one routine matches and a signature is required."""


class ProcedureDiscoveryError(ProcoraError):
    """Procedure metadata could not be discovered."""


class ProcedureParameterError(ProcoraError, ValueError):
    """Supplied parameters do not match live procedure metadata."""


class UnsupportedParameterError(ProcoraError):
    """A driver needs an application-specific parameter adapter."""


class ProcedureExecutionError(ProcoraError):
    """The database failed to execute a stored procedure."""
