import tomllib
from dataclasses import replace

from demi.config.codec import decode_settings, dumps_settings, encode_settings, loads_settings
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
