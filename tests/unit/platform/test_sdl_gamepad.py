from dataclasses import dataclass, field

import pytest

from demi.domain.gamepad import GamepadButton, GamepadDevice
from demi.platform import sdl_gamepad
from demi.platform.sdl_gamepad import SdlGamepadBackend

sdl2 = sdl_gamepad.sdl2


@dataclass
class FakeSdlCalls:
    """Mutable SDL function responses for backend tests."""

    attached: bool = True
    joystick_count: int = 1
    open_count: int = 0
    close_count: int = 0
    pressed: set[int] = field(default_factory=set)


def _install_sdl_functions(monkeypatch: pytest.MonkeyPatch, calls: FakeSdlCalls) -> None:
    controller = object()
    monkeypatch.setattr(sdl2, "SDL_InitSubSystem", lambda _flags: 0)
    monkeypatch.setattr(sdl2, "SDL_GameControllerEventState", lambda _state: None)
    monkeypatch.setattr(sdl2, "SDL_PumpEvents", lambda: None)
    monkeypatch.setattr(sdl2, "SDL_GameControllerUpdate", lambda: None)
    monkeypatch.setattr(sdl2, "SDL_NumJoysticks", lambda: calls.joystick_count)
    monkeypatch.setattr(sdl2, "SDL_IsGameController", lambda _index: True)

    def open_controller(_index: int) -> object:
        """Return one fake controller and count each open."""
        calls.open_count += 1
        return controller

    def attached(_controller: object) -> bool:
        """Return the configured attachment state."""
        return calls.attached

    def close_controller(_controller: object) -> None:
        """Record each controller close."""
        calls.close_count += 1

    def button(_controller: object, constant: int) -> int:
        """Return a pressed state for configured SDL button constants."""
        return int(constant in calls.pressed)

    monkeypatch.setattr(sdl2, "SDL_GameControllerOpen", open_controller)
    monkeypatch.setattr(sdl2, "SDL_GameControllerGetAttached", attached)
    monkeypatch.setattr(sdl2, "SDL_GameControllerClose", close_controller)
    monkeypatch.setattr(sdl2, "SDL_GameControllerGetButton", button)
    monkeypatch.setattr(sdl2, "SDL_GameControllerGetAxis", lambda _controller, _axis: 0)
    monkeypatch.setattr(sdl2, "SDL_QuitSubSystem", lambda _flags: None)


def test_backend_opens_first_controller_and_reopens_after_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = FakeSdlCalls(pressed={sdl2.SDL_CONTROLLER_BUTTON_A})
    _install_sdl_functions(monkeypatch, calls)
    backend = SdlGamepadBackend()

    first = backend.poll()
    calls.attached = False
    second = backend.poll()

    assert first.connected is True
    assert GamepadButton.SOUTH in first.buttons
    assert second.connected is True
    assert calls.open_count == 2
    assert calls.close_count == 1


def test_backend_returns_neutral_when_initialization_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sdl2, "SDL_InitSubSystem", lambda _flags: -1)

    backend = SdlGamepadBackend()

    assert backend.poll().connected is False


def test_backend_lists_connected_devices_without_exposing_device_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    devices = (
        ("First controller", "guid-first", 41),
        ("Second controller", "guid-second", 72),
    )

    _install_sdl_functions(monkeypatch, FakeSdlCalls(joystick_count=len(devices)))
    monkeypatch.setattr(
        sdl2, "SDL_GameControllerNameForIndex", lambda index: devices[index][0].encode()
    )
    monkeypatch.setattr(sdl2, "SDL_JoystickGetDeviceGUID", lambda index: devices[index][1])
    monkeypatch.setattr(
        sdl2,
        "SDL_JoystickGetGUIDString",
        lambda guid, buffer, _size: setattr(buffer, "value", guid.encode()),
    )
    monkeypatch.setattr(sdl2, "SDL_JoystickGetDeviceInstanceID", lambda index: devices[index][2])
    backend = SdlGamepadBackend()

    listed = backend.connected_devices()

    assert listed == (
        GamepadDevice(name="First controller", persistent_id="guid-first", instance_id=41),
        GamepadDevice(name="Second controller", persistent_id="guid-second", instance_id=72),
    )
    assert all("index" not in device.__dataclass_fields__ for device in listed)
