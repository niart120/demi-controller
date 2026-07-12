"""Schema migration boundary for settings documents."""

from collections.abc import Mapping

from demi.domain.settings import SCHEMA

from .errors import ConfigurationError, UnsupportedSchemaError


def migrate_settings(raw: Mapping[str, object]) -> Mapping[str, object]:
    """Pass current settings through or reject an unsupported schema.

    Args:
        raw: Decoded TOML mapping.

    Returns:
        The current-schema mapping, unchanged.

    Raises:
        ConfigurationError: If the input is not a mapping.
        UnsupportedSchemaError: If the schema is not ``demi.settings/v1``.
    """
    if not isinstance(raw, Mapping):
        raise ConfigurationError
    if raw.get("schema") != SCHEMA:
        raise UnsupportedSchemaError
    return raw
