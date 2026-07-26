"""SDL2 GameController adapter backed by PySDL2."""

import warnings
from ctypes import create_string_buffer
from types import ModuleType

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"Using SDL2 binaries from pysdl2-dll.*",
        category=UserWarning,
    )
    import sdl2

from demi.domain.gamepad import GamepadButton, GamepadDevice, GamepadState
from demi.input.gamepad import (
    GamepadInputPort,
    GamepadSelectionPort,
    apply_stick_dead_zone,
    normalize_trigger,
)


class SdlGamepadBackend(GamepadInputPort, GamepadSelectionPort):
    """Poll the first SDL GameController without creating SDL UI resources.

    The backend initializes only SDL's GameController subsystem. A missing SDL
    runtime, initialization failure, or absent controller is represented as a
    neutral state so the rest of the application keeps accepting keyboard and
    mouse input.
    """

    def __init__(self, bindings: ModuleType = sdl2) -> None:
        """Initialize the SDL GameController subsystem when available."""
        self._sdl = bindings
        self._controller: object | None = None
        self._selected_persistent_id: str | None = None
        self._closed = False
        self._initialized = bindings.SDL_InitSubSystem(bindings.SDL_INIT_GAMECONTROLLER) == 0
        if self._initialized:
            bindings.SDL_GameControllerEventState(bindings.SDL_ENABLE)

    def poll(self) -> GamepadState:
        """Return the first connected controller state without blocking."""
        if self._closed or not self._initialized:
            return GamepadState.neutral()
        self._sdl.SDL_PumpEvents()
        self._sdl.SDL_GameControllerUpdate()
        if self._controller is not None and not self._sdl.SDL_GameControllerGetAttached(
            self._controller
        ):
            self._close_controller()
            return GamepadState.neutral()
        if self._controller is None:
            self._controller = self._open_first_controller()
        controller = self._controller
        if controller is None:
            return GamepadState.neutral()
        return GamepadState(
            connected=True,
            buttons=frozenset(
                button
                for button, constant in _BUTTON_CONSTANTS.items()
                if self._sdl.SDL_GameControllerGetButton(controller, getattr(self._sdl, constant))
            ),
            left_stick=apply_stick_dead_zone(
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_LEFTX
                ),
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_LEFTY
                ),
            ),
            right_stick=apply_stick_dead_zone(
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_RIGHTX
                ),
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_RIGHTY
                ),
            ),
            left_trigger=normalize_trigger(
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_TRIGGERLEFT
                )
            ),
            right_trigger=normalize_trigger(
                self._sdl.SDL_GameControllerGetAxis(
                    controller, self._sdl.SDL_CONTROLLER_AXIS_TRIGGERRIGHT
                )
            ),
        )

    def connected_devices(self) -> tuple[GamepadDevice, ...]:
        """Return connected SDL GameControllers without device indexes."""
        if self._closed or not self._initialized:
            return ()
        return tuple(
            device
            for device_index in range(self._sdl.SDL_NumJoysticks())
            if (device := self._device_at(device_index)) is not None
        )

    def select_device(self, persistent_id: str | None) -> None:
        """Select one saved GUID or return to automatic selection.

        A selection change closes the current SDL handle so the next poll
        opens only the newly selected device.
        """
        if persistent_id is not None and (not isinstance(persistent_id, str) or not persistent_id):
            raise ValueError
        if persistent_id == self._selected_persistent_id:
            return
        self._selected_persistent_id = persistent_id
        self._close_controller()

    def close(self) -> None:
        """Close the selected controller and SDL GameController subsystem once."""
        if self._closed:
            return
        self._closed = True
        self._close_controller()
        if self._initialized:
            self._sdl.SDL_QuitSubSystem(self._sdl.SDL_INIT_GAMECONTROLLER)
            self._initialized = False

    def _open_first_controller(self) -> object | None:
        devices = tuple(
            (device_index, device)
            for device_index in range(self._sdl.SDL_NumJoysticks())
            if (device := self._device_at(device_index)) is not None
        )
        selected_persistent_id = self._selected_persistent_id
        if selected_persistent_id is not None:
            matching_indexes = [
                device_index
                for device_index, device in devices
                if device.persistent_id == selected_persistent_id
            ]
            if len(matching_indexes) == 1:
                return self._sdl.SDL_GameControllerOpen(matching_indexes[0])
        return self._sdl.SDL_GameControllerOpen(devices[0][0]) if devices else None

    def _device_at(self, device_index: int) -> GamepadDevice | None:
        if not self._sdl.SDL_IsGameController(device_index):
            return None
        raw_name = self._sdl.SDL_GameControllerNameForIndex(device_index)
        name = raw_name.decode(errors="replace") if raw_name is not None else "Unknown controller"
        buffer = create_string_buffer(33)
        self._sdl.SDL_JoystickGetGUIDString(
            self._sdl.SDL_JoystickGetDeviceGUID(device_index), buffer, len(buffer)
        )
        persistent_id = buffer.value.decode()
        instance_id = self._sdl.SDL_JoystickGetDeviceInstanceID(device_index)
        if not persistent_id or instance_id < 0:
            return None
        return GamepadDevice(
            name=name,
            persistent_id=persistent_id,
            instance_id=instance_id,
        )

    def _close_controller(self) -> None:
        controller = self._controller
        if controller is not None:
            self._sdl.SDL_GameControllerClose(controller)
            self._controller = None


_BUTTON_CONSTANTS = {
    GamepadButton.SOUTH: "SDL_CONTROLLER_BUTTON_A",
    GamepadButton.EAST: "SDL_CONTROLLER_BUTTON_B",
    GamepadButton.WEST: "SDL_CONTROLLER_BUTTON_X",
    GamepadButton.NORTH: "SDL_CONTROLLER_BUTTON_Y",
    GamepadButton.DPAD_UP: "SDL_CONTROLLER_BUTTON_DPAD_UP",
    GamepadButton.DPAD_DOWN: "SDL_CONTROLLER_BUTTON_DPAD_DOWN",
    GamepadButton.DPAD_LEFT: "SDL_CONTROLLER_BUTTON_DPAD_LEFT",
    GamepadButton.DPAD_RIGHT: "SDL_CONTROLLER_BUTTON_DPAD_RIGHT",
    GamepadButton.LEFT_SHOULDER: "SDL_CONTROLLER_BUTTON_LEFTSHOULDER",
    GamepadButton.RIGHT_SHOULDER: "SDL_CONTROLLER_BUTTON_RIGHTSHOULDER",
    GamepadButton.LEFT_STICK: "SDL_CONTROLLER_BUTTON_LEFTSTICK",
    GamepadButton.RIGHT_STICK: "SDL_CONTROLLER_BUTTON_RIGHTSTICK",
    GamepadButton.BACK: "SDL_CONTROLLER_BUTTON_BACK",
    GamepadButton.START: "SDL_CONTROLLER_BUTTON_START",
    GamepadButton.GUIDE: "SDL_CONTROLLER_BUTTON_GUIDE",
}
