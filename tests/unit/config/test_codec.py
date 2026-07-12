import tomllib
from dataclasses import replace
from typing import cast

import pytest

from demi.config.codec import decode_settings, dumps_settings, encode_settings, loads_settings
from demi.config.errors import ConfigurationError, UnsupportedSchemaError
from demi.config.migrations import migrate_settings
from demi.domain.mapping import Binding, BindingTarget, InputProfile
from demi.domain.settings import AppSettings, ControllerColorSettings


def test_default_settings_round_trip_through_toml() -> None:
    settings = AppSettings.default()

    encoded = encode_settings(settings)
    restored = decode_settings(encoded)
    text = dumps_settings(settings)
    loaded_from_text = loads_settings(text)

    assert restored == settings
    assert loaded_from_text == settings
    assert tomllib.loads(text)["schema"] == "demi.settings/v1"


def test_codec_preserves_custom_colors_and_inverted_binding() -> None:
    profile = InputProfile(
        id="custom",
        name="Custom",
        builtin=False,
        bindings=(
            Binding(source="MOUSE:RIGHT", target=BindingTarget.BUTTON_ZL, inverted=True),
            Binding(source="KEY:W", target=BindingTarget.LEFT_STICK_UP, amount=0.75),
        ),
    )
    settings = replace(
        AppSettings.default(),
        active_profile="custom",
        controller_colors=ControllerColorSettings(
            body="#abcdef",
            buttons="#010203",
            left_grip="#040506",
            right_grip="#070809",
        ),
        profiles=(profile,),
    )

    restored = loads_settings(dumps_settings(settings))

    assert restored == settings
    assert restored.profiles[0].bindings[0].inverted is True
    assert restored.profiles[0].bindings[1].amount == 0.75


def test_unknown_schema_is_rejected_by_the_migration_boundary() -> None:
    raw = encode_settings(AppSettings.default())
    raw["schema"] = "demi.settings/v2"

    with pytest.raises(UnsupportedSchemaError):
        migrate_settings(raw)
    with pytest.raises(UnsupportedSchemaError):
        decode_settings(raw)


def test_unknown_fields_and_invalid_values_are_rejected() -> None:
    raw = encode_settings(AppSettings.default())
    raw["future_setting"] = True
    with pytest.raises(ConfigurationError):
        decode_settings(raw)

    raw = encode_settings(AppSettings.default())
    connection = cast("dict[str, object]", raw["connection"])
    connection["diagnostic_level"] = "TRACE"
    with pytest.raises(ConfigurationError):
        decode_settings(raw)

    raw = encode_settings(AppSettings.default())
    input_settings = cast("dict[str, object]", raw["input"])
    mouse = cast("dict[str, object]", input_settings["mouse"])
    mouse["pitch_limit_degrees"] = 90.0
    with pytest.raises(ConfigurationError):
        decode_settings(raw)
