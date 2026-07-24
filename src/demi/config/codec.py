"""TOML codec for the current Project_Demi settings schema."""

import tomllib
from collections.abc import Mapping
from dataclasses import replace
from typing import cast

import tomli_w

from demi.domain.mapping import Binding, BindingTarget, InputProfile
from demi.domain.settings import (
    SCHEMA,
    AppSettings,
    ConnectionSettings,
    ControllerColorSettings,
    ControllerType,
    DiagnosticLevel,
    InputSettings,
    LocalActions,
    MouseSettings,
    UiLanguage,
    UiSettings,
    WindowSettings,
)

from .errors import ConfigurationError, UnsupportedSchemaError
from .migrations import migrate_settings


def _require_table(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ConfigurationError
    return cast("Mapping[str, object]", value)


def _require_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ConfigurationError
    return cast("list[object]", value)


def _require_string(value: object) -> str:
    if not isinstance(value, str):
        raise ConfigurationError
    return value


def _require_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError
    return value


def _require_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError
    return value


def _require_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError
    return float(value)


def _check_keys(
    table: Mapping[str, object],
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    keys = set(table)
    if not required <= keys or not keys <= required | optional:
        raise ConfigurationError


def _controller_type(value: object) -> ControllerType:
    try:
        return ControllerType(_require_string(value))
    except (TypeError, ValueError):
        raise ConfigurationError from None


def _diagnostic_level(value: object) -> DiagnosticLevel:
    try:
        return DiagnosticLevel(_require_string(value))
    except (TypeError, ValueError):
        raise ConfigurationError from None


def _ui_language(value: object) -> UiLanguage:
    try:
        return UiLanguage(_require_string(value))
    except (TypeError, ValueError):
        raise ConfigurationError from None


def _decode_binding(raw: object) -> Binding:
    table = _require_table(raw)
    _check_keys(table, frozenset({"source", "target"}), frozenset({"amount", "inverted"}))
    try:
        target = BindingTarget(_require_string(table["target"]))
    except (TypeError, ValueError):
        raise ConfigurationError from None
    amount = _require_float(table.get("amount", 1.0))
    inverted = _require_bool(table.get("inverted", False))
    try:
        return Binding(
            source=_require_string(table["source"]),
            target=target,
            amount=amount,
            inverted=inverted,
        )
    except ValueError:
        raise ConfigurationError from None


def _decode_profile(raw: object) -> InputProfile:
    table = _require_table(raw)
    _check_keys(table, frozenset({"id", "name", "builtin", "bindings"}))
    try:
        return InputProfile(
            id=_require_string(table["id"]),
            name=_require_string(table["name"]),
            builtin=_require_bool(table["builtin"]),
            bindings=tuple(_decode_binding(item) for item in _require_list(table["bindings"])),
        )
    except ValueError:
        raise ConfigurationError from None


def encode_settings(settings: AppSettings) -> dict[str, object]:
    """Convert validated settings into a TOML-compatible mapping.

    Args:
        settings: Settings snapshot to encode.

    Returns:
        A mapping containing only the current schema fields.
    """
    return {
        "schema": settings.schema,
        "active_profile": settings.active_profile,
        "ui": {"language": settings.ui.language.value},
        "window": {
            "width": settings.window.width,
            "height": settings.window.height,
            "maximized": settings.window.maximized,
        },
        "connection": {
            "adapter_id": settings.connection.adapter_id,
            "controller": settings.connection.controller.value,
            "reconnect_on_start": settings.connection.reconnect_on_start,
            "diagnostic_level": settings.connection.diagnostic_level.value,
        },
        "controller": {
            "colors": {
                "body": settings.controller_colors.body,
                "buttons": settings.controller_colors.buttons,
                "left_grip": settings.controller_colors.left_grip,
                "right_grip": settings.controller_colors.right_grip,
            }
        },
        "input": {
            "evaluation_interval_ms": settings.input.evaluation_interval_ms,
            "circular_stick_limit": settings.input.circular_stick_limit,
            "mouse": {
                "gyro_enabled": settings.input.mouse.gyro_enabled,
                "horizontal_sensitivity": settings.input.mouse.horizontal_sensitivity,
                "vertical_sensitivity": settings.input.mouse.vertical_sensitivity,
                "invert_x": settings.input.mouse.invert_x,
                "invert_y": settings.input.mouse.invert_y,
                "pitch_limit_degrees": settings.input.mouse.pitch_limit_degrees,
            },
        },
        "local_actions": {
            "toggle_capture": list(settings.local_actions.toggle_capture),
            "quit": list(settings.local_actions.quit),
            "connection": list(settings.local_actions.connection),
            "release_capture": list(settings.local_actions.release_capture),
        },
        "profiles": [
            {
                "id": profile.id,
                "name": profile.name,
                "builtin": profile.builtin,
                "bindings": [
                    {
                        "source": binding.source,
                        "target": binding.target.value,
                        "amount": binding.amount,
                        "inverted": binding.inverted,
                    }
                    for binding in profile.bindings
                ],
            }
            for profile in settings.profiles
        ],
    }


def decode_settings(raw: Mapping[str, object]) -> AppSettings:
    """Decode and validate a current-schema settings mapping.

    Args:
        raw: TOML mapping containing a complete ``demi.settings/v1`` document.

    Returns:
        A validated immutable settings snapshot.

    Raises:
        ConfigurationError: If the mapping is malformed or violates a domain
            constraint.
        UnsupportedSchemaError: If the schema is not the current schema.
    """
    raw = migrate_settings(raw)
    _check_keys(
        raw,
        frozenset(
            {
                "schema",
                "active_profile",
                "window",
                "connection",
                "controller",
                "input",
                "local_actions",
                "profiles",
            }
        ),
        frozenset({"ui"}),
    )
    schema = _require_string(raw["schema"])
    if schema != SCHEMA:
        raise UnsupportedSchemaError

    ui = _require_table(raw.get("ui", {"language": UiLanguage.ENGLISH.value}))
    _check_keys(ui, frozenset({"language"}))

    window = _require_table(raw["window"])
    _check_keys(window, frozenset({"width", "height", "maximized"}))
    connection = _require_table(raw["connection"])
    _check_keys(
        connection,
        frozenset(
            {
                "adapter_id",
                "controller",
                "reconnect_on_start",
                "diagnostic_level",
            }
        ),
        frozenset({"bond_slot", "timeout_seconds"}),
    )
    controller = _require_table(raw["controller"])
    _check_keys(controller, frozenset({"colors"}))
    colors = _require_table(controller["colors"])
    _check_keys(colors, frozenset({"body", "buttons", "left_grip", "right_grip"}))
    input_settings = _require_table(raw["input"])
    _check_keys(
        input_settings, frozenset({"evaluation_interval_ms", "circular_stick_limit", "mouse"})
    )
    mouse = _require_table(input_settings["mouse"])
    _check_keys(
        mouse,
        frozenset(
            {
                "gyro_enabled",
                "horizontal_sensitivity",
                "vertical_sensitivity",
                "invert_y",
                "pitch_limit_degrees",
            }
        ),
        frozenset({"invert_x"}),
    )
    local_actions = _require_table(raw["local_actions"])
    _check_keys(
        local_actions,
        frozenset({"toggle_capture", "quit", "release_capture"}),
        frozenset({"connection"}),
    )

    try:
        settings = AppSettings(
            schema=schema,
            active_profile=_require_string(raw["active_profile"]),
            ui=UiSettings(language=_ui_language(ui["language"])),
            window=WindowSettings(
                width=_require_int(window["width"]),
                height=_require_int(window["height"]),
                maximized=_require_bool(window["maximized"]),
            ),
            connection=ConnectionSettings(
                adapter_id=_require_string(connection["adapter_id"]),
                controller=_controller_type(connection["controller"]),
                reconnect_on_start=_require_bool(connection["reconnect_on_start"]),
                diagnostic_level=_diagnostic_level(connection["diagnostic_level"]),
            ),
            controller_colors=ControllerColorSettings(
                body=_require_string(colors["body"]),
                buttons=_require_string(colors["buttons"]),
                left_grip=_require_string(colors["left_grip"]),
                right_grip=_require_string(colors["right_grip"]),
            ),
            input=InputSettings(
                evaluation_interval_ms=_require_int(input_settings["evaluation_interval_ms"]),
                circular_stick_limit=_require_bool(input_settings["circular_stick_limit"]),
                mouse=MouseSettings(
                    gyro_enabled=_require_bool(mouse["gyro_enabled"]),
                    horizontal_sensitivity=_require_float(mouse["horizontal_sensitivity"]),
                    vertical_sensitivity=_require_float(mouse["vertical_sensitivity"]),
                    invert_x=_require_bool(mouse.get("invert_x", False)),
                    invert_y=_require_bool(mouse["invert_y"]),
                    pitch_limit_degrees=_require_float(mouse["pitch_limit_degrees"]),
                ),
            ),
            local_actions=LocalActions(
                toggle_capture=tuple(
                    _require_string(value)
                    for value in _require_list(local_actions["toggle_capture"])
                ),
                quit=tuple(
                    _require_string(value) for value in _require_list(local_actions["quit"])
                ),
                connection=tuple(
                    _require_string(value)
                    for value in _require_list(
                        local_actions.get("connection", ["CTRL+RETURN", "CTRL+ENTER"])
                    )
                ),
                release_capture=tuple(
                    _require_string(value)
                    for value in _require_list(local_actions["release_capture"])
                ),
            ),
            profiles=tuple(_decode_profile(item) for item in _require_list(raw["profiles"])),
        )
        return _migrate_legacy_input_defaults(settings)
    except (TypeError, ValueError):
        raise ConfigurationError from None


def _migrate_legacy_input_defaults(settings: AppSettings) -> AppSettings:
    local_actions = settings.local_actions
    if local_actions.release_capture == ("F12",):
        local_actions = replace(local_actions, release_capture=("F4",))

    profiles = tuple(
        replace(
            profile,
            bindings=tuple(
                replace(binding, source="KEY:F1")
                if binding.source == "KEY:ESCAPE" and binding.target is BindingTarget.BUTTON_HOME
                else binding
                for binding in profile.bindings
            ),
        )
        if profile.id == "default" and profile.name == "Default" and profile.builtin
        else profile
        for profile in settings.profiles
    )
    return replace(settings, local_actions=local_actions, profiles=profiles)


def dumps_settings(settings: AppSettings) -> str:
    """Serialize settings as UTF-8 TOML text.

    Args:
        settings: Validated settings snapshot.

    Returns:
        TOML text using the current schema and complete binding arrays.
    """
    return tomli_w.dumps(encode_settings(settings))


def loads_settings(text: str) -> AppSettings:
    """Parse TOML text and decode it as current-schema settings.

    Args:
        text: UTF-8 TOML document.

    Returns:
        Validated immutable settings.

    Raises:
        ConfigurationError: The text is malformed or violates a setting
            constraint.
        UnsupportedSchemaError: The document uses an unknown schema.
    """
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        raise ConfigurationError from None
    return decode_settings(raw)
