"""Window specifications and the pyglet window factory."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.presentation import PresentationStore
from demi.application.settings_editor import SettingsEditor
from demi.application.state import ConnectionState
from demi.domain.errors import DomainValueError
from demi.domain.physical_input import KeySource
from demi.domain.settings import AppSettings, DiagnosticLevel, WindowSettings
from demi.input.publisher import InputPublisher
from demi.input.pyglet_backend import PygletInputBackend

from .controller_view import ControllerView
from .dialogs import DialogViewModel, ModalAction, ModalRenderer
from .status_bar import StatusBar
from .toolbar import Toolbar

if TYPE_CHECKING:
    from pyglet.window import Window


@dataclass(frozen=True, slots=True)
class WindowSpec:
    """Validated dimensions and creation options for the main window.

    Raises:
        DomainValueError: A dimension or option violates the window contract.
    """

    width: int = 960
    height: int = 640
    min_width: int = 800
    min_height: int = 520
    caption: str = "Project Demi"
    resizable: bool = True
    visible: bool = False
    vsync: bool = True
    maximized: bool = False

    def __post_init__(self) -> None:
        """Validate window dimensions and creation flags."""
        values = (self.width, self.height, self.min_width, self.min_height)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise DomainValueError
        if self.width < self.min_width or self.height < self.min_height:
            raise DomainValueError
        if self.min_width < 1 or self.min_height < 1:
            raise DomainValueError
        if not isinstance(self.caption, str) or not self.caption.strip():
            raise DomainValueError
        if not isinstance(self.resizable, bool) or not isinstance(self.visible, bool):
            raise DomainValueError
        if not isinstance(self.vsync, bool) or not isinstance(self.maximized, bool):
            raise DomainValueError


class PygletWindowPort(Protocol):
    """Window operations consumed by the application event bridge."""

    width: int
    height: int

    def push_handlers(self, *objects: object) -> None:
        """Register event handler objects."""

    def clear(self) -> None:
        """Clear the current drawing surface."""

    def set_visible(self, visible: bool = True) -> None:
        """Show or hide the configured window."""

    def close(self) -> None:
        """Request native window closure."""


class ClockScheduler(Protocol):
    """Subset of pyglet clock scheduling used by the application."""

    def schedule_interval(self, callback: Callable[[float], None], interval: float) -> None:
        """Schedule a callback at a fixed interval."""

    def unschedule(self, callback: Callable[[float], None]) -> None:
        """Remove a previously scheduled callback."""


class GuiActions(Protocol):
    """Main-thread application actions requested by GUI controls."""

    def toggle_capture(self) -> bool:
        """Toggle input capture."""

    def connection_action(self) -> None:
        """Perform the state-dependent connection action."""

    def open_settings(self, kind: DialogKind) -> bool:
        """Open one editable settings modal."""

    def save_settings(self) -> bool:
        """Save the active settings modal draft."""

    def cancel_settings(self) -> bool:
        """Discard the active settings modal draft."""

    def confirm_pairing(self) -> bool:
        """Start pairing after its explicit confirmation."""

    def cancel_pairing(self) -> bool:
        """Return pairing confirmation to its connection draft."""

    def request_pairing(self) -> bool:
        """Open the explicit pairing confirmation for the active draft."""

    def defer_color_reconnect(self) -> None:
        """Keep locally saved colors without changing the connected controller."""

    def request_color_reconnect(self) -> bool:
        """Request explicit controller recreation with saved colors."""

    def rescan_adapters(self) -> None:
        """Request a fresh asynchronous USB adapter discovery."""


class ModalKeyCodes(Protocol):
    """Pyglet key constants used while a modal owns keyboard input."""

    ESCAPE: int
    ENTER: int
    SPACE: int
    TAB: int
    F12: int
    C: int
    Q: int
    MOD_CTRL: int
    MOD_SHIFT: int
    MOD_ALT: int
    MOD_COMMAND: int
    MOD_OPTION: int
    BACKSPACE: int

    def symbol_string(self, symbol: int) -> str:
        """Return pyglet's symbolic name for a key value."""


class BatchPort(Protocol):
    """Subset of a pyglet batch used by the application chrome."""

    def draw(self) -> None:
        """Draw all labels in the batch."""


class TextLabel(Protocol):
    """Subset of a pyglet label used by the application chrome."""

    text: str
    y: float


def create_window(spec: WindowSpec | None = None) -> "Window":
    """Create a pyglet window from a validated window specification.

    Args:
        spec: Dimensions and creation options for the main window.

    Returns:
        A configured pyglet window with the minimum size applied.

    Raises:
        DomainValueError: The window specification is invalid.
        Exception: Pyglet raises an environment-specific error when a display
            or OpenGL context cannot be created.
    """
    if spec is None:
        spec = WindowSpec()

    from pyglet.window import Window  # noqa: PLC0415

    window = Window(
        width=spec.width,
        height=spec.height,
        caption=spec.caption,
        resizable=spec.resizable,
        visible=spec.visible,
        vsync=spec.vsync,
    )
    window.set_minimum_size(spec.min_width, spec.min_height)
    if spec.maximized:
        window.maximize()
    return window


class PygletApplication:
    """Connect the window, input backend, publisher, and view on one thread."""

    def __init__(
        self,
        *,
        window: PygletWindowPort,
        coordinator: CaptureCoordinator,
        backend: PygletInputBackend,
        view: ControllerView,
        toolbar: Toolbar,
        status_bar: StatusBar,
        clock: ClockScheduler | None = None,
        connection_state: ConnectionState = ConnectionState.READY,
        adapter_label: str = "なし",
        evaluation_interval_ms: int = InputPublisher.default_evaluation_interval_ms,
        presentation: PresentationStore | None = None,
        actions: GuiActions | None = None,
        event_pump: Callable[[], int | None] | None = None,
        settings_provider: Callable[[], AppSettings] | None = None,
        dialogs: DialogManager | None = None,
        editor_provider: Callable[[], SettingsEditor | None] | None = None,
        modal_renderer: ModalRenderer | None = None,
        modal_key_codes: ModalKeyCodes | None = None,
        on_shutdown_requested: Callable[[WindowSettings | None], None] | None = None,
        window_maximized: bool = False,
    ) -> None:
        """Initialize the main-thread application event bridge."""
        self._window = window
        self._coordinator = coordinator
        self._backend = backend
        self._view = view
        self._toolbar = toolbar
        self._status_bar = status_bar
        if clock is None:
            from pyglet import clock as pyglet_clock  # noqa: PLC0415

            self._clock = cast("ClockScheduler", pyglet_clock)
        else:
            self._clock = clock
        self._connection_state = connection_state
        self._adapter_label = adapter_label
        self._evaluation_interval_ms = evaluation_interval_ms
        self._presentation = presentation
        self._actions = actions
        self._event_pump = event_pump
        self._settings_provider = settings_provider
        self._dialogs = dialogs
        self._editor_provider = editor_provider
        self._modal_renderer = modal_renderer
        self._modal_key_codes = modal_key_codes
        self._on_shutdown_requested = on_shutdown_requested
        self._window_maximized = window_maximized
        self._last_live_settings: AppSettings | None = None
        self._binding_capture_index: int | None = None
        self._started = False
        self._closing = False
        self._text_edit_target: str | None = None
        self._text_edit_buffer = ""
        self._drawn_recovery_notice: str | None = None
        self._chrome_batch: BatchPort | None = None
        self._toolbar_label: TextLabel | None = None
        self._status_label: TextLabel | None = None

    @property
    def started(self) -> bool:
        """Return whether the application callback is scheduled."""
        return self._started

    def start(self) -> None:
        """Install event handlers and schedule the configured input evaluation."""
        if self._started:
            return
        self._sync_live_settings()
        self._backend.install(self._window)
        self._window.push_handlers(self)
        self._clock.schedule_interval(
            self._evaluate,
            self._evaluation_interval_ms / 1000.0,
        )
        self._window.set_visible(True)
        self._started = True

    def stop(self) -> None:
        """Unschedule evaluation and leave capture in a neutral state."""
        if not self._started:
            return
        self._clock.unschedule(self._evaluate)
        self._coordinator.stop_capture()
        self._started = False

    def run(self) -> None:
        """Start the application and enter pyglet's default event loop."""
        from pyglet import app as pyglet_app  # noqa: PLC0415

        self.start()
        pyglet_app.run()

    def toggle_capture(self) -> bool:
        """Start or stop capture through the coordinator-owned transition."""
        if self._actions is not None:
            return self._actions.toggle_capture()
        return self._coordinator.toggle_capture()

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> bool | None:
        """Route enabled toolbar clicks to application actions before input mapping."""
        del modifiers
        model = self._modal_model()
        if model is not None and model.visible:
            if self._binding_capture_index is not None:
                self._capture_binding_mouse(button)
                return True
            renderer = self._modal_renderer
            if renderer is not None:
                renderer.controls(model, width=self._window.width, height=self._window.height)
                control = renderer.hit_test(
                    float(x),
                    float(y),
                    width=self._window.width,
                    height=self._window.height,
                )
                if control is not None:
                    self._dispatch_modal_action(control.action, control.target)
            return True
        self._sync_chrome()
        control = self._toolbar.hit_test(
            float(x),
            float(y),
            width=self._window.width,
            height=self._window.height,
        )
        if control is None:
            return None
        if control.action == "capture":
            self.toggle_capture()
            return True
        if self._actions is None:
            return None
        if control.action == "connection":
            self._actions.connection_action()
        elif control.action == "mapping":
            self._actions.open_settings(DialogKind.MAPPING)
        elif control.action == "connection_settings":
            self._actions.open_settings(DialogKind.CONNECTION)
        elif control.action == "colors":
            self._actions.open_settings(DialogKind.COLORS)
        else:
            return None
        return True

    def on_key_press(self, symbol: int, modifiers: int) -> bool | None:
        """Keep modal editing keys out of controller input mappings.

        F12 remains unhandled here so the lower-level input backend can always
        neutralize capture.
        """
        keys = self._modal_key_codes_or_load()
        modal_model = self._modal_model()
        if modal_model is not None and modal_model.visible:
            if symbol == keys.F12:
                return None
            if self._binding_capture_index is not None:
                if symbol == keys.ESCAPE:
                    self._binding_capture_index = None
                else:
                    self._capture_binding_key(symbol, modifiers)
                return True
            if self._text_edit_target is not None:
                if symbol == keys.ESCAPE:
                    self._clear_text_edit()
                elif symbol == keys.ENTER:
                    self._commit_text_edit()
                elif symbol == keys.BACKSPACE:
                    self._text_edit_buffer = self._text_edit_buffer[:-1]
                return True
            if symbol == keys.ESCAPE:
                action = (
                    ModalAction.DEFER_COLOR_RECONNECT
                    if modal_model.color_reconnect_prompt
                    else ModalAction.CANCEL
                )
                self._dispatch_modal_action(action)
            elif symbol in (keys.ENTER, keys.SPACE):
                kind = self._dialogs.model.kind if self._dialogs is not None else DialogKind.NONE
                if modal_model.color_reconnect_prompt:
                    action = ModalAction.REQUEST_COLOR_RECONNECT
                elif kind is DialogKind.PAIRING_CONFIRMATION:
                    action = ModalAction.CONFIRM_PAIRING
                else:
                    action = ModalAction.SAVE
                self._dispatch_modal_action(action)
            return True
        if self._dialogs is not None and self._dialogs.model.visible:
            if symbol == keys.F12:
                return None
            if symbol == keys.ESCAPE:
                self._dispatch_modal_action(ModalAction.CANCEL)
            elif symbol in (keys.ENTER, keys.SPACE):
                self._dispatch_modal_action(ModalAction.SAVE)
            return True
        if symbol == keys.F12:
            return None
        settings = self._settings_provider() if self._settings_provider is not None else None
        if settings is None:
            return None
        if any(
            self._matches_shortcut(shortcut, symbol, modifiers)
            for shortcut in settings.local_actions.release_capture
        ):
            self._coordinator.stop_capture()
            return True
        if any(
            self._matches_shortcut(shortcut, symbol, modifiers)
            for shortcut in settings.local_actions.quit
        ):
            self._request_window_close()
            return True
        if any(
            self._matches_shortcut(shortcut, symbol, modifiers)
            for shortcut in settings.local_actions.toggle_capture
        ):
            self.toggle_capture()
            return True
        return None

    def on_key_release(self, symbol: int, modifiers: int) -> bool | None:
        """Consume modal key releases except the reserved F12 release."""
        del modifiers
        if not self._modal_is_open() or symbol == self._modal_key_codes_or_load().F12:
            return None
        return True

    def on_text(self, text: str) -> bool | None:
        """Reserve text input for the active modal instead of controller mappings."""
        if not self._modal_is_open():
            return None
        if self._text_edit_target is not None:
            self._text_edit_buffer += text
        return True

    def on_draw(self) -> None:
        """Render the latest frame and the toolbar/status text."""
        self._sync_live_settings()
        frame = self._coordinator.last_frame
        if frame is not None:
            self._view.update(frame)
        self._sync_chrome()
        self._window.clear()
        self._view.draw(float(self._window.width), float(self._window.height))
        self._draw_chrome()
        self._acknowledge_drawn_recovery_notice()
        self._draw_modal()

    def on_close(self) -> None:
        """Stop scheduled evaluation when the window is closing."""
        if self._closing:
            return
        self._closing = True
        self._stop_schedule()
        callback = self._on_shutdown_requested
        if callback is None:
            self._coordinator.begin_shutdown()
            return
        callback(self.snapshot_window_state())

    def on_maximize(self) -> None:
        """Remember the native maximize event for later settings persistence."""
        self._window_maximized = True

    def on_restore(self) -> None:
        """Remember that the native window left its maximized state."""
        self._window_maximized = False

    def snapshot_window_state(self) -> WindowSettings | None:
        """Return valid current window dimensions for ordered shutdown."""
        try:
            return WindowSettings(
                width=self._window.width,
                height=self._window.height,
                maximized=self._window_maximized,
            )
        except DomainValueError:
            return None

    def _evaluate(self, dt_seconds: float) -> None:
        del dt_seconds
        if self._event_pump is not None:
            self._event_pump()
        self._sync_live_settings()
        self._coordinator.evaluate()

    def _modal_is_open(self) -> bool:
        """Return whether a modal currently owns GUI input."""
        model = self._modal_model()
        return (model is not None and model.visible) or (
            self._dialogs is not None and self._dialogs.model.visible
        )

    def _modal_model(self) -> DialogViewModel | None:
        """Build one modal view using the latest editor and presentation state."""
        renderer = self._modal_renderer
        dialogs = self._dialogs
        if renderer is None or dialogs is None:
            return None
        editor = self._editor_provider() if self._editor_provider is not None else None
        presentation = self._presentation.model if self._presentation is not None else None
        return renderer.view_model(
            dialogs,
            editor,
            adapters=() if presentation is None else presentation.adapters,
            color_reconnect_pending=(
                False if presentation is None else presentation.color_reconnect_pending
            ),
            text_edit_target=self._text_edit_target,
            text_edit_value=self._text_edit_buffer,
        )

    def _request_window_close(self) -> None:
        """Run the close callback before asking pyglet to close natively."""
        if not self._closing:
            self.on_close()
        self._window.close()

    def _stop_schedule(self) -> None:
        """Remove the input callback without choosing a capture transition."""
        if not self._started:
            return
        self._clock.unschedule(self._evaluate)
        self._started = False

    def _dispatch_modal_action(self, action: ModalAction, target: str | None = None) -> None:
        """Route one visible modal action without exposing it to input mapping."""
        editor = self._editor_provider() if self._editor_provider is not None else None
        if action is ModalAction.CAPTURE_BINDING and target is not None:
            try:
                self._binding_capture_index = int(target)
            except ValueError:
                self._binding_capture_index = None
            return
        if (
            action is ModalAction.TOGGLE_BINDING_INVERSION
            and target is not None
            and editor is not None
        ):
            try:
                index = int(target)
                binding = editor.draft.profiles[0].bindings[index]
                editor.update_binding(index, inverted=not binding.inverted)
            except (IndexError, ValueError):
                return
            return
        if action is ModalAction.SELECT_ADAPTER and target is not None and editor is not None:
            editor.update_connection(adapter_id=target)
            return
        if action is ModalAction.RESET_PROFILE and editor is not None:
            editor.reset_profile()
            return
        if action is ModalAction.EDIT_FIELD and target is not None and editor is not None:
            self._begin_field_edit(target, editor)
            return
        actions = self._actions
        if actions is None:
            return
        kind = self._dialogs.model.kind if self._dialogs is not None else DialogKind.NONE
        if action is ModalAction.SAVE:
            actions.save_settings()
        elif action is ModalAction.CANCEL:
            if kind is DialogKind.PAIRING_CONFIRMATION:
                actions.cancel_pairing()
            else:
                actions.cancel_settings()
        elif action is ModalAction.CONFIRM_PAIRING:
            actions.confirm_pairing()
        elif action is ModalAction.CANCEL_PAIRING:
            actions.cancel_pairing()
        elif action is ModalAction.REQUEST_PAIRING:
            actions.request_pairing()
        elif action is ModalAction.DEFER_COLOR_RECONNECT:
            actions.defer_color_reconnect()
        elif action is ModalAction.REQUEST_COLOR_RECONNECT:
            actions.request_color_reconnect()
        elif action is ModalAction.RESCAN_ADAPTERS:
            actions.rescan_adapters()

    def _capture_binding_key(self, symbol: int, modifiers: int) -> None:
        """Commit one modal-owned keyboard event as a binding source."""
        index = self._binding_capture_index
        editor = self._editor_provider() if self._editor_provider is not None else None
        if index is None or editor is None:
            self._binding_capture_index = None
            return
        keys = self._modal_key_codes_or_load()
        key_name = keys.symbol_string(symbol).upper()
        if key_name.startswith("_") and key_name[1:].isdigit():
            key_name = key_name[1:]
        source = KeySource(key_name, self._event_modifier_names(modifiers)).canonical
        try:
            editor.update_binding(index, source=source)
        except DomainValueError:
            return
        self._binding_capture_index = None

    def _capture_binding_mouse(self, button: int) -> None:
        """Commit one modal-owned mouse click as a binding source."""
        index = self._binding_capture_index
        editor = self._editor_provider() if self._editor_provider is not None else None
        if index is None or editor is None:
            self._binding_capture_index = None
            return
        source = {
            1: "MOUSE:LEFT",
            2: "MOUSE:MIDDLE",
            4: "MOUSE:RIGHT",
        }.get(button, f"MOUSE:BUTTON_{button.bit_length()}")
        try:
            editor.update_binding(index, source=source)
        except DomainValueError:
            return
        self._binding_capture_index = None

    def _begin_field_edit(self, target: str, editor: SettingsEditor) -> None:
        """Toggle boolean fields or prepare validated text entry for one draft field."""
        mouse = editor.draft.input.mouse
        if target == "mouse.gyro_enabled":
            editor.update_mouse(gyro_enabled=not mouse.gyro_enabled)
            return
        if target == "mouse.invert_y":
            editor.update_mouse(invert_y=not mouse.invert_y)
            return
        if target == "input.circular_stick_limit":
            editor.update_input(circular_stick_limit=not editor.draft.input.circular_stick_limit)
            return
        if target == "connection.reconnect_on_start":
            editor.update_connection(
                reconnect_on_start=not editor.draft.connection.reconnect_on_start
            )
            return
        if target == "connection.diagnostic_level":
            levels = tuple(DiagnosticLevel)
            current = editor.draft.connection.diagnostic_level
            editor.update_connection(
                diagnostic_level=levels[(levels.index(current) + 1) % len(levels)]
            )
            return
        self._text_edit_target = target
        self._text_edit_buffer = ""

    def _commit_text_edit(self) -> bool:
        """Validate and commit one text field without closing its modal draft."""
        target = self._text_edit_target
        editor = self._editor_provider() if self._editor_provider is not None else None
        if target is None or editor is None:
            self._clear_text_edit()
            return False
        value = self._text_edit_buffer.strip()
        try:
            if target == "mouse.horizontal_sensitivity":
                editor.update_mouse(horizontal_sensitivity=float(value))
            elif target == "mouse.vertical_sensitivity":
                editor.update_mouse(vertical_sensitivity=float(value))
            elif target == "mouse.pitch_limit_degrees":
                editor.update_mouse(pitch_limit_degrees=float(value))
            elif target == "input.evaluation_interval_ms":
                editor.update_input(evaluation_interval_ms=int(value))
            elif target == "connection.bond_slot":
                editor.update_connection(bond_slot=value)
            elif target == "connection.timeout_seconds":
                editor.update_connection(timeout_seconds=float(value))
            elif target == "connection.diagnostic_level":
                editor.update_connection(diagnostic_level=DiagnosticLevel(value.upper()))
            elif target == "color.body":
                editor.update_color("body", value)
            elif target == "color.buttons":
                editor.update_color("buttons", value)
            elif target == "color.left_grip":
                editor.update_color("left_grip", value)
            elif target == "color.right_grip":
                editor.update_color("right_grip", value)
            else:
                return False
        except (DomainValueError, ValueError):
            return False
        self._clear_text_edit()
        return True

    def _clear_text_edit(self) -> None:
        """Discard a pending text buffer while retaining the existing draft value."""
        self._text_edit_target = None
        self._text_edit_buffer = ""

    def _modal_key_codes_or_load(self) -> ModalKeyCodes:
        """Load pyglet key constants only when a modal needs keyboard input."""
        if self._modal_key_codes is None:
            from pyglet.window import key  # noqa: PLC0415

            self._modal_key_codes = cast("ModalKeyCodes", key)
        return self._modal_key_codes

    def _matches_shortcut(self, shortcut: str, symbol: int, modifiers: int) -> bool:
        """Return whether one persisted local-action shortcut matches this event."""
        parts = shortcut.upper().split("+")
        if not parts or any(not part for part in parts):
            return False
        keys = self._modal_key_codes_or_load()
        key_name = keys.symbol_string(symbol).upper()
        if key_name.startswith("_") and key_name[1:].isdigit():
            key_name = key_name[1:]
        if key_name != parts[-1]:
            return False
        return self._event_modifier_names(modifiers) == frozenset(parts[:-1])

    def _event_modifier_names(self, modifiers: int) -> frozenset[str]:
        """Normalize pyglet modifier bits into persisted shortcut names."""
        keys = self._modal_key_codes_or_load()
        return frozenset(
            name
            for mask, name in (
                (keys.MOD_CTRL, "CTRL"),
                (keys.MOD_SHIFT, "SHIFT"),
                (keys.MOD_ALT, "ALT"),
                (keys.MOD_COMMAND, "COMMAND"),
                (keys.MOD_OPTION, "OPTION"),
            )
            if modifiers & mask
        )

    def _sync_live_settings(self) -> None:
        provider = self._settings_provider
        if provider is None:
            return
        settings = provider()
        if settings == self._last_live_settings:
            return
        next_interval_ms = settings.input.evaluation_interval_ms
        interval_changed = next_interval_ms != self._evaluation_interval_ms
        if interval_changed and self._started:
            self._clock.unschedule(self._evaluate)
        self._evaluation_interval_ms = next_interval_ms
        self._view.set_colors(settings.controller_colors)
        self._status_bar.set_evaluation_interval_ms(next_interval_ms)
        self._last_live_settings = settings
        if interval_changed and self._started:
            self._clock.schedule_interval(
                self._evaluate,
                self._evaluation_interval_ms / 1000.0,
            )

    def _sync_chrome(self) -> None:
        connection_state = self._connection_state
        adapter_label = self._adapter_label
        warning: str | None = None
        adapter_available = True
        self._drawn_recovery_notice = None
        if self._presentation is not None:
            presentation = self._presentation.model
            connection_state = presentation.connection_state
            adapter_label = presentation.adapter_label
            warning = presentation.error or presentation.warning or None
            if not warning and presentation.recovery_notice is not None:
                warning = presentation.recovery_notice
                self._drawn_recovery_notice = warning
            adapter_available = bool(presentation.adapters)
        self._toolbar.update(
            app_state=self._coordinator.app_state,
            connection_state=connection_state,
            focused=self._coordinator.focused,
            dialog_open=self._modal_is_open(),
            adapter_available=adapter_available,
        )
        self._status_bar.update(
            adapter_label=adapter_label,
            connection_state=connection_state,
            app_state=self._coordinator.app_state,
            preview_only=self._coordinator.is_captured
            and connection_state is not ConnectionState.CONNECTED,
            warning=warning,
        )

    def _acknowledge_drawn_recovery_notice(self) -> None:
        """Clear a recovery notice only after the status bar has rendered it."""
        notice = self._drawn_recovery_notice
        if notice is None or self._presentation is None:
            return
        self._presentation.acknowledge_recovery_notice(notice)
        self._drawn_recovery_notice = None

    def _draw_modal(self) -> None:
        renderer = self._modal_renderer
        model = self._modal_model()
        if renderer is None or model is None or not model.visible:
            return
        renderer.draw(
            model,
            width=self._window.width,
            height=self._window.height,
        )
        if self._binding_capture_index is None:
            return
        from pyglet.text import Label  # noqa: PLC0415

        prompt = "入力待ち: 次のキーまたはマウスボタンを押してください (Esc で取消)"
        Label(prompt, x=72, y=self._window.height / 2.0, color=(255, 220, 140, 255)).draw()

    def _draw_chrome(self) -> None:
        if self._chrome_batch is None:
            from pyglet.graphics import Batch  # noqa: PLC0415
            from pyglet.text import Label  # noqa: PLC0415

            batch = Batch()
            self._chrome_batch = cast("BatchPort", batch)
            self._toolbar_label = cast(
                "TextLabel",
                Label(
                    "",
                    x=16,
                    y=self._window.height - 32,
                    batch=batch,
                ),
            )
            self._status_label = cast("TextLabel", Label("", x=16, y=12, batch=batch))
        if self._toolbar_label is not None:
            self._toolbar_label.text = self._toolbar.model.connection_label
            self._toolbar_label.y = self._window.height - 32
        if self._status_label is not None:
            self._status_label.text = self._status_bar.model.text
        if self._chrome_batch is not None:
            self._chrome_batch.draw()
        from pyglet import shapes  # noqa: PLC0415
        from pyglet.text import Label  # noqa: PLC0415

        for control in self._toolbar.controls(
            width=self._window.width,
            height=self._window.height,
        ):
            color = (50, 98, 150) if control.enabled else (75, 75, 75)
            shapes.Rectangle(
                control.x,
                control.y,
                control.width,
                control.height,
                color=color,
            ).draw()
            Label(
                control.label,
                x=control.x + 8,
                y=control.y + 8,
                color=(255, 255, 255, 255),
            ).draw()
