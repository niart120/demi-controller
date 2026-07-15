from dataclasses import dataclass, field

from demi.domain.physical_input import PhysicalInputState
from demi.platform.windows_mouse_hook import (
    WM_LBUTTONDOWN,
    WM_LBUTTONUP,
    WM_MOUSEMOVE,
    WM_MOUSEWHEEL,
    WM_RBUTTONDOWN,
    WM_XBUTTONDOWN,
    WM_XBUTTONUP,
    WindowsMouseInputSuppressor,
)


@dataclass
class FakeMouseHookRegistrar:
    """Record low-level hook registration without calling Win32."""

    callbacks: list[object] = field(default_factory=list)
    removed_handles: list[int] = field(default_factory=list)

    def install(self, callback: object) -> int:
        """Store the supplied callback and return a stable hook handle."""
        self.callbacks.append(callback)
        return 0x1234

    def remove(self, handle: int) -> None:
        """Record one logical hook removal."""
        self.removed_handles.append(handle)


def test_active_capture_suppresses_external_mouse_messages_and_maps_buttons() -> None:
    state = PhysicalInputState()
    registrar = FakeMouseHookRegistrar()
    suppressor = WindowsMouseInputSuppressor(
        registrar=registrar,
        on_button_pressed=state.press_mouse_button,
        on_button_released=state.release_mouse_button,
    )

    suppressor.start()

    assert suppressor.handle_message(WM_MOUSEMOVE) is True
    assert suppressor.handle_message(WM_LBUTTONDOWN) is True
    assert state.is_source_active("MOUSE:LEFT") is True
    assert suppressor.handle_message(WM_LBUTTONUP) is True
    assert state.is_source_active("MOUSE:LEFT") is False
    assert suppressor.handle_message(WM_RBUTTONDOWN) is True
    assert state.is_source_active("MOUSE:RIGHT") is True
    assert suppressor.handle_message(WM_XBUTTONDOWN, 1 << 16) is True
    assert state.is_source_active("MOUSE:BUTTON_4") is True
    assert suppressor.handle_message(WM_XBUTTONUP, 1 << 16) is True
    assert state.is_source_active("MOUSE:BUTTON_4") is False
    assert suppressor.handle_message(WM_XBUTTONDOWN, 2 << 16) is True
    assert state.is_source_active("MOUSE:BUTTON_5") is True
    assert suppressor.handle_message(WM_XBUTTONUP, 2 << 16) is True
    assert state.is_source_active("MOUSE:BUTTON_5") is False
    assert suppressor.handle_message(WM_MOUSEWHEEL) is True
    assert registrar.callbacks

    suppressor.stop()

    assert registrar.removed_handles == [0x1234]


def test_inactive_capture_leaves_mouse_messages_and_input_state_unchanged() -> None:
    state = PhysicalInputState()
    suppressor = WindowsMouseInputSuppressor(
        registrar=FakeMouseHookRegistrar(),
        on_button_pressed=state.press_mouse_button,
        on_button_released=state.release_mouse_button,
    )

    assert suppressor.handle_message(WM_LBUTTONDOWN) is False
    assert state.is_source_active("MOUSE:LEFT") is False
