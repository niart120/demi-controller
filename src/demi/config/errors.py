"""Errors raised while decoding or storing application settings."""


class ConfigurationError(ValueError):
    """Raised when a settings document is invalid."""


class UnsupportedSchemaError(ConfigurationError):
    """Raised when a settings document uses an unknown schema version."""


class SettingsPersistenceError(ConfigurationError):
    """Raised when settings cannot be read, written, or atomically replaced."""
