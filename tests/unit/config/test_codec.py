import tomllib
from dataclasses import replace
from typing import cast

import pytest

from demi.config.codec import decode_settings, dumps_settings, encode_settings, loads_settings
from demi.config.errors import ConfigurationError, UnsupportedSchemaError
from demi.config.migrations import migrate_settings
from demi.domain.mapping import Binding, BindingTarget, InputProfile
from demi.domain.settings import (
    AppSettings,
    ControllerColorSettings,
    InputSettings,
    MouseSettings,
    UiLanguage,
    UiSettings,
)


def test_default_settings_round_trip_through_toml() -> None:
    settings = AppSettings.default()

    encoded = encode_settings(settings)
    restored = decode_settings(encoded)
    text = dumps_settings(settings)
    loaded_from_text = loads_settings(text)

    assert restored == settings
    assert loaded_from_text == settings
    assert tomllib.loads(text)["schema"] == "demi.settings/v1"
    local_actions = cast("dict[str, object]", encoded["local_actions"])
    assert local_actions["connection"] == ["CTRL+RETURN", "CTRL+ENTER"]


def test_codec_supplies_connection_shortcuts_for_existing_v1_settings() -> None:
    raw = encode_settings(AppSettings.default())
    local_actions = cast("dict[str, object]", raw["local_actions"])
    del local_actions["connection"]

    restored = decode_settings(raw)

    assert restored.local_actions.connection == ("CTRL+RETURN", "CTRL+ENTER")


def test_codec_omits_removed_connection_choices_and_ignores_their_legacy_values() -> None:
    encoded = encode_settings(AppSettings.default())
    connection = cast("dict[str, object]", encoded["connection"])

    assert set(connection) == {
        "adapter_id",
        "controller",
        "reconnect_on_start",
        "diagnostic_level",
    }

    connection["bond_slot"] = {"legacy": "value"}
    connection["timeout_seconds"] = "legacy"

    restored = decode_settings(encoded)
    reencoded = encode_settings(restored)
    reencoded_connection = cast("dict[str, object]", reencoded["connection"])

    assert restored == AppSettings.default()
    assert "bond_slot" not in reencoded_connection
    assert "timeout_seconds" not in reencoded_connection


def test_codec_migrates_only_exact_legacy_home_and_release_defaults() -> None:
    legacy = encode_settings(AppSettings.default())
    legacy_actions = cast("dict[str, object]", legacy["local_actions"])
    legacy_actions["release_capture"] = ["F12"]
    legacy_profiles = cast("list[object]", legacy["profiles"])
    legacy_profile = cast("dict[str, object]", legacy_profiles[0])
    legacy_bindings = cast("list[object]", legacy_profile["bindings"])
    legacy_home = next(
        cast("dict[str, object]", binding)
        for binding in legacy_bindings
        if cast("dict[str, object]", binding)["target"] == "BUTTON:HOME"
    )
    legacy_home["source"] = "KEY:ESCAPE"

    migrated = decode_settings(legacy)

    migrated_home = next(
        binding
        for binding in migrated.profiles[0].bindings
        if binding.target is BindingTarget.BUTTON_HOME
    )
    assert migrated_home.source == "KEY:F1"
    assert migrated.local_actions.release_capture == ("F4",)

    customized = encode_settings(AppSettings.default())
    customized_actions = cast("dict[str, object]", customized["local_actions"])
    customized_actions["release_capture"] = ["F8"]
    customized_profiles = cast("list[object]", customized["profiles"])
    customized_profile = cast("dict[str, object]", customized_profiles[0])
    customized_bindings = cast("list[object]", customized_profile["bindings"])
    customized_home = next(
        cast("dict[str, object]", binding)
        for binding in customized_bindings
        if cast("dict[str, object]", binding)["target"] == "BUTTON:HOME"
    )
    customized_home["source"] = "KEY:F2"

    preserved = decode_settings(customized)

    preserved_home = next(
        binding
        for binding in preserved.profiles[0].bindings
        if binding.target is BindingTarget.BUTTON_HOME
    )
    assert preserved_home.source == "KEY:F2"
    assert preserved.local_actions.release_capture == ("F8",)


def test_codec_supplies_english_for_existing_v1_settings_and_round_trips_languages() -> None:
    raw = encode_settings(AppSettings.default())
    raw.pop("ui")

    restored = decode_settings(raw)

    assert restored.ui.language is UiLanguage.ENGLISH

    for language in UiLanguage:
        settings = replace(AppSettings.default(), ui=UiSettings(language=language))

        encoded = encode_settings(settings)
        decoded = decode_settings(encoded)

        assert encoded["ui"] == {"language": language.value}
        assert decoded == settings


def test_codec_supplies_disabled_horizontal_inversion_for_existing_v1_settings() -> None:
    raw = encode_settings(AppSettings.default())
    input_settings = cast("dict[str, object]", raw["input"])
    mouse = cast("dict[str, object]", input_settings["mouse"])
    mouse.pop("invert_x", None)
    mouse["invert_y"] = True

    restored = decode_settings(raw)

    assert restored.input.mouse.invert_x is False
    assert restored.input.mouse.invert_y is True


def test_codec_round_trips_independent_mouse_axis_inversions() -> None:
    settings = replace(
        AppSettings.default(),
        input=InputSettings(mouse=MouseSettings(invert_x=True, invert_y=True)),
    )

    encoded = encode_settings(settings)
    restored = decode_settings(encoded)
    input_settings = cast("dict[str, object]", encoded["input"])
    mouse = cast("dict[str, object]", input_settings["mouse"])

    assert mouse["invert_x"] is True
    assert mouse["invert_y"] is True
    assert restored == settings


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


def test_codec_preserves_configurable_imu_diagnostic_targets() -> None:
    profile = InputProfile(
        id="diagnostic",
        name="Diagnostic",
        builtin=False,
        bindings=(
            Binding(source="KEY:U", target=BindingTarget.GYRO_Y_NEGATIVE),
            Binding(source="MOUSE:MIDDLE", target=BindingTarget.ACCEL_ZERO),
        ),
    )
    settings = replace(
        AppSettings.default(),
        active_profile=profile.id,
        profiles=(profile,),
    )

    restored = loads_settings(dumps_settings(settings))

    assert restored == settings


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
