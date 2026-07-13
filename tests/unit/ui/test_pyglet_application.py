from collections.abc import Callable
from dataclasses import dataclass, field, replace

from demi.application.coordinator import CaptureCoordinator
from demi.application.dialogs import DialogKind, DialogManager
from demi.application.presentation import AdapterOption, PresentationStore
from demi.application.settings_editor import SettingsEditor
from demi.application.state import ConnectionState
from demi.domain.controller import ControllerFrame
from demi.domain.settings import AppSettings, LocalActions, WindowSettings
from demi.input.publisher import InputPublisher
from demi.input.pyglet_backend import PygletInputBackend
from demi.ui.controller_view import ControllerView
from demi.ui.dialogs import ModalRenderer
from demi.ui.status_bar import StatusBar
from demi.ui.toolbar import Toolbar
from demi.ui.window import PygletApplication


@dataclass
class FakeClock:
    """Clock scheduler recording the application callback."""

    now_ns: int = 1_000_000_000
    scheduled: list[tuple[Callable[[float], None], float]] = field(default_factory=list)
    unscheduled: list[Callable[[float], None]] = field(default_factory=list)

    def monotonic_ns(self) -> int:
        """Return the configured monotonic timestamp."""
        return self.now_ns

    def schedule_interval(self, callback: Callable[[float], None], interval: float) -> None:
        """Record one scheduled callback."""
        self.scheduled.append((callback, interval))

    def unschedule(self, callback: Callable[[float], None]) -> None:
        """Record an unschedule request."""
        self.unscheduled.append(callback)


@dataclass
class FakeWindow:
    """Window boundary recording event handlers and draw calls."""

    width: int = 960
    height: int = 640
    handlers: list[object] = field(default_factory=list)
    clear_calls: int = 0
    visible_calls: list[bool] = field(default_factory=list)
    close_calls: int = 0

    def push_handlers(self, *objects: object) -> None:
        """Record installed event handlers."""
        self.handlers.extend(objects)

    def clear(self) -> None:
        """Record a clear request."""
        self.clear_calls += 1

    def set_visible(self, visible: bool = True) -> None:
        """Record visibility changes."""
        self.visible_calls.append(visible)

    def set_exclusive_mouse(self, exclusive: bool = True) -> None:
        """Satisfy the coordinator window port."""
        del exclusive

    def close(self) -> None:
        """Record a native close request."""
        self.close_calls += 1


@dataclass
class FakeSink:
    """In-memory frame sink for application wiring tests."""

    frames: list[ControllerFrame] = field(default_factory=list)

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Store the offered frame."""
        self.frames.append(frame)


class RecordingControllerView(ControllerView):
    """Controller view double that records frames without pyglet drawing."""

    def __init__(self) -> None:
        """Initialize the recording view with the production display model."""
        super().__init__()
        self.frames: list[ControllerFrame] = []

    def update(self, frame: ControllerFrame) -> None:
        """Record and apply one frame without changing display semantics."""
        self.frames.append(frame)
        super().update(frame)

    def draw(self, width: float, height: float) -> None:
        """Skip pyglet drawing while retaining the update path under test."""
        del width, height


class DrawFreeApplication(PygletApplication):
    """Application double that keeps the frame route while skipping pyglet chrome."""

    def _draw_chrome(self) -> None:
        return

    def _draw_modal(self) -> None:
        return


@dataclass
class OrderedSink:
    """Frame sink that records evaluation order with a GUI event pump."""

    order: list[str]

    def offer_frame(self, frame: ControllerFrame) -> None:
        """Record delivery after the application evaluates the frame."""
        del frame
        self.order.append("frame")


@dataclass
class FakeActions:
    """GUI action port recording toolbar requests."""

    capture_toggles: int = 0
    connection_requests: int = 0
    opened_dialogs: list[DialogKind] = field(default_factory=list)
    saves: int = 0
    cancels: int = 0
    pairing_confirms: int = 0
    pairing_cancels: int = 0
    color_reconnects: int = 0
    color_reconnect_deferrals: int = 0
    adapter_rescans: int = 0

    def toggle_capture(self) -> bool:
        """Record a capture request."""
        self.capture_toggles += 1
        return True

    def connection_action(self) -> None:
        """Record a connection request."""
        self.connection_requests += 1

    def open_settings(self, kind: DialogKind) -> bool:
        """Record an editable dialog request."""
        self.opened_dialogs.append(kind)
        return True

    def save_settings(self) -> bool:
        """Record a settings save request."""
        self.saves += 1
        return True

    def cancel_settings(self) -> bool:
        """Record a settings cancel request."""
        self.cancels += 1
        return True

    def confirm_pairing(self) -> bool:
        """Record an explicit pairing confirmation."""
        self.pairing_confirms += 1
        return True

    def cancel_pairing(self) -> bool:
        """Record a return from pairing confirmation to its draft."""
        self.pairing_cancels += 1
        return True

    def request_pairing(self) -> bool:
        """Record a transition to pairing confirmation."""
        return True

    def request_color_reconnect(self) -> bool:
        """Record an explicit runtime color recreation request."""
        self.color_reconnects += 1
        return True

    def defer_color_reconnect(self) -> None:
        """Record a choice to keep the current runtime colors for now."""
        self.color_reconnect_deferrals += 1

    def rescan_adapters(self) -> None:
        """Record a request to rediscover USB adapters."""
        self.adapter_rescans += 1


class FakeModalKeyCodes:
    """Key constants shared by the modal and input-backend tests."""

    ESCAPE = 1
    ENTER = 2
    SPACE = 3
    TAB = 4
    F12 = 5
    F = 6
    K = 7
    C = 8
    Q = 9
    BACKSPACE = 10
    MOD_CTRL = 1
    MOD_SHIFT = 2
    MOD_ALT = 4
    MOD_COMMAND = 8
    MOD_OPTION = 16

    def symbol_string(self, symbol: int) -> str:
        """Return a stable symbolic name for input-backend normalization."""
        return {
            self.ESCAPE: "ESCAPE",
            self.ENTER: "ENTER",
            self.SPACE: "SPACE",
            self.TAB: "TAB",
            self.F12: "F12",
            self.F: "F",
            self.K: "K",
            self.C: "C",
            self.Q: "Q",
            self.BACKSPACE: "BACKSPACE",
        }[symbol]


def test_application_installs_backend_and_schedules_eight_millisecond_evaluation() -> None:
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    backend = PygletInputBackend(coordinator)
    window = FakeWindow()
    application = PygletApplication(
        window=window,
        coordinator=coordinator,
        backend=backend,
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        clock=clock,
    )

    application.start()

    assert application.started is True
    assert backend in window.handlers
    assert application in window.handlers
    assert len(clock.scheduled) == 1
    assert window.visible_calls == [True]
    callback, interval = clock.scheduled[0]
    assert interval == 0.008

    callback(0.008)
    assert coordinator.last_frame is sink.frames[-1]

    application.stop()
    assert application.started is False
    assert clock.unscheduled == [callback]


def test_application_draws_the_exact_frame_offered_to_the_runtime() -> None:
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    view = RecordingControllerView()
    application = DrawFreeApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=view,
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        clock=clock,
    )

    application.start()
    callback, _interval = clock.scheduled[0]
    callback(0.008)
    application.on_draw()

    assert coordinator.last_frame is sink.frames[-1]
    assert view.frames[-1] is sink.frames[-1]


def test_application_pumps_worker_events_before_evaluating_input() -> None:
    order: list[str] = []
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=OrderedSink(order))
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        clock=clock,
        event_pump=lambda: order.append("event"),
    )

    application.start()
    callback, _interval = clock.scheduled[0]
    callback(0.008)

    assert order == ["event", "frame"]


def test_application_pumps_events_before_evaluation_and_routes_toolbar_clicks() -> None:
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    backend = PygletInputBackend(coordinator)
    toolbar = Toolbar()
    actions = FakeActions()
    pumped: list[bool] = []
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=backend,
        view=ControllerView(),
        toolbar=toolbar,
        status_bar=StatusBar(),
        clock=clock,
        actions=actions,
        event_pump=lambda: pumped.append(True),
    )

    application.start()
    callback, _ = clock.scheduled[0]
    callback(0.008)
    capture = next(
        control
        for control in toolbar.controls(width=960, height=640)
        if control.action == "capture"
    )

    assert pumped == [True]
    assert application.on_mouse_press(int(capture.x + 1), int(capture.y + 1), 1, 0) is True
    assert actions.capture_toggles == 1


def test_application_routes_configured_local_shortcuts_to_capture_and_shutdown() -> None:
    key_codes = FakeModalKeyCodes()
    window = FakeWindow()
    clock = FakeClock()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=clock, sink=FakeSink()),
        window=window,
    )
    actions = FakeActions()
    snapshots = []
    application = PygletApplication(
        window=window,
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        clock=clock,
        actions=actions,
        settings_provider=AppSettings.default,
        modal_key_codes=key_codes,
        on_shutdown_requested=snapshots.append,
    )
    application.start()

    assert application.on_key_press(key_codes.C, key_codes.MOD_CTRL) is True
    assert actions.capture_toggles == 1
    assert application.on_key_press(key_codes.Q, key_codes.MOD_CTRL) is True
    assert window.close_calls == 1
    assert len(snapshots) == 1
    assert clock.unscheduled == [clock.scheduled[0][0]]
    assert application.on_key_press(key_codes.F12, 0) is None


def test_application_uses_presentation_state_and_configured_interval() -> None:
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    presentation = PresentationStore()
    presentation.set_connection(
        ConnectionState.CONNECTED,
        adapter_id="usb:0",
        adapter_label="Adapter 0",
    )
    toolbar = Toolbar()
    status_bar = StatusBar(evaluation_interval_ms=16)
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=toolbar,
        status_bar=status_bar,
        clock=clock,
        presentation=presentation,
        evaluation_interval_ms=16,
    )

    application.start()
    application._sync_chrome()

    assert clock.scheduled[0][1] == 0.016
    assert toolbar.model.connection_label == "接続済み"
    assert "Adapter: Adapter 0" in status_bar.model.text


def test_application_displays_a_recovery_notice_once_in_the_status_bar() -> None:
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    presentation = PresentationStore()
    presentation.set_recovery_notice("設定を復旧しました")
    status_bar = StatusBar()
    application = DrawFreeApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=status_bar,
        presentation=presentation,
    )

    application.on_draw()

    assert status_bar.model.warning == "設定を復旧しました"
    assert presentation.model.recovery_notice is None

    application.on_draw()

    assert status_bar.model.warning == ""


def test_application_keeps_a_recovery_notice_until_it_can_render() -> None:
    presentation = PresentationStore()
    presentation.set_recovery_notice("設定を復旧しました")
    presentation.set_warning("接続を確認してください")
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    status_bar = StatusBar()
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=status_bar,
        presentation=presentation,
    )

    application._sync_chrome()

    assert status_bar.model.warning == "接続を確認してください"
    assert presentation.model.recovery_notice == "設定を復旧しました"


def test_application_applies_saved_colors_and_interval_without_restarting() -> None:
    settings = AppSettings.default()
    current_settings = [settings]
    sink = FakeSink()
    clock = FakeClock()
    publisher = InputPublisher(clock=clock, sink=sink)
    coordinator = CaptureCoordinator(publisher=publisher, window=FakeWindow())
    view = ControllerView()
    status_bar = StatusBar()
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=view,
        toolbar=Toolbar(),
        status_bar=status_bar,
        clock=clock,
        settings_provider=lambda: current_settings[0],
    )

    application.start()
    callback, _interval = clock.scheduled[0]
    current_settings[0] = replace(
        settings,
        controller_colors=replace(settings.controller_colors, body="#ABCDEF"),
        input=replace(settings.input, evaluation_interval_ms=16),
    )
    callback(0.008)

    assert view.colors.body == "#ABCDEF"
    assert status_bar.model.evaluation_interval_ms == 16
    assert clock.unscheduled == [callback]
    assert clock.scheduled[-1][1] == 0.016


def test_application_consumes_modal_clicks_before_controller_input() -> None:
    sink = FakeSink()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        window=FakeWindow(),
    )
    assert coordinator.start_capture() is True
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.MAPPING) is True
    renderer = ModalRenderer()
    actions = FakeActions()
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        editor_provider=lambda: SettingsEditor(AppSettings.default()),
        modal_renderer=renderer,
        actions=actions,
    )
    model = renderer.controls(
        renderer.view_model(dialogs, SettingsEditor(AppSettings.default())),
        width=960,
        height=640,
    )
    cancel = next(control for control in model if control.action.value == "cancel")

    assert application.on_mouse_press(int(cancel.x + 1), int(cancel.y + 1), 1, 0) is True
    assert actions.cancels == 1
    assert coordinator.publisher.state.held_mouse_buttons == set()


def test_application_routes_pairing_confirmation_controls_without_saving_a_draft() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.PAIRING_CONFIRMATION) is True
    renderer = ModalRenderer()
    actions = FakeActions()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        modal_renderer=renderer,
        actions=actions,
    )
    controls = renderer.controls(renderer.view_model(dialogs), width=960, height=640)
    back = next(control for control in controls if control.action.value == "cancel_pairing")
    confirm = next(control for control in controls if control.action.value == "confirm_pairing")

    assert application.on_mouse_press(int(back.x + 1), int(back.y + 1), 1, 0) is True
    assert application.on_mouse_press(int(confirm.x + 1), int(confirm.y + 1), 1, 0) is True
    assert actions.pairing_cancels == 1
    assert actions.pairing_confirms == 1
    assert actions.saves == 0


def test_application_routes_explicit_color_reconnect_choice() -> None:
    dialogs = DialogManager()
    renderer = ModalRenderer()
    actions = FakeActions()
    presentation = PresentationStore()
    presentation.set_color_reconnect_pending(True)
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        modal_renderer=renderer,
        actions=actions,
        presentation=presentation,
    )
    controls = renderer.controls(
        renderer.view_model(dialogs, color_reconnect_pending=True),
        width=960,
        height=640,
    )
    defer = next(control for control in controls if control.action.value == "defer_color_reconnect")
    recreate = next(
        control for control in controls if control.action.value == "request_color_reconnect"
    )

    assert application.on_mouse_press(int(defer.x + 1), int(defer.y + 1), 1, 0) is True
    assert application.on_mouse_press(int(recreate.x + 1), int(recreate.y + 1), 1, 0) is True
    assert actions.color_reconnect_deferrals == 1
    assert actions.color_reconnects == 1
    assert actions.saves == 0


def test_application_edits_mapping_draft_controls_without_publishing_input() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.MAPPING) is True
    editor = SettingsEditor(AppSettings.default())
    renderer = ModalRenderer()
    key_codes = FakeModalKeyCodes()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    assert coordinator.start_capture() is True
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        editor_provider=lambda: editor,
        modal_renderer=renderer,
        modal_key_codes=key_codes,
    )
    controls = renderer.controls(renderer.view_model(dialogs, editor), width=960, height=640)
    capture = next(
        control
        for control in controls
        if control.action.value == "capture_binding" and control.target == "0"
    )
    invert = next(
        control
        for control in controls
        if control.action.value == "toggle_binding_inversion" and control.target == "0"
    )

    assert application.on_mouse_press(int(capture.x + 1), int(capture.y + 1), 1, 0) is True
    assert application.on_key_press(key_codes.K, key_codes.MOD_CTRL) is True
    assert application.on_mouse_press(int(invert.x + 1), int(invert.y + 1), 1, 0) is True

    binding = editor.draft.profiles[0].bindings[0]
    assert binding.source == "KEY:CTRL+K"
    assert binding.inverted is True
    assert coordinator.publisher.state.held_keys == set()


def test_application_commits_color_text_to_the_open_draft_only() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.COLORS) is True
    editor = SettingsEditor(AppSettings.default())
    renderer = ModalRenderer()
    key_codes = FakeModalKeyCodes()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        editor_provider=lambda: editor,
        modal_renderer=renderer,
        modal_key_codes=key_codes,
    )
    controls = renderer.controls(renderer.view_model(dialogs, editor), width=960, height=640)
    body = next(
        control
        for control in controls
        if control.action.value == "edit_field" and control.target == "color.body"
    )

    assert application.on_mouse_press(int(body.x + 1), int(body.y + 1), 1, 0) is True
    assert application.on_text("#abcdef") is True
    assert application.on_key_press(key_codes.ENTER, 0) is True

    assert editor.draft.controller_colors.body == "#ABCDEF"
    assert coordinator.publisher.state.held_keys == set()


def test_application_routes_connection_modal_adapter_and_rescan_actions() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.CONNECTION) is True
    editor = SettingsEditor(AppSettings.default())
    renderer = ModalRenderer()
    presentation = PresentationStore()
    presentation.set_adapters((AdapterOption("usb:0", "専用アダプター"),))
    actions = FakeActions()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        editor_provider=lambda: editor,
        modal_renderer=renderer,
        presentation=presentation,
        actions=actions,
    )
    controls = renderer.controls(
        renderer.view_model(dialogs, editor, adapters=presentation.model.adapters),
        width=960,
        height=640,
    )
    adapter = next(
        control
        for control in controls
        if control.action.value == "select_adapter" and control.target == "usb:0"
    )
    rescan = next(control for control in controls if control.action.value == "rescan_adapters")

    assert application.on_mouse_press(int(adapter.x + 1), int(adapter.y + 1), 1, 0) is True
    assert application.on_mouse_press(int(rescan.x + 1), int(rescan.y + 1), 1, 0) is True
    assert editor.draft.connection.adapter_id == "usb:0"
    assert actions.adapter_rescans == 1


def test_application_commits_modal_text_edits_to_the_draft() -> None:
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.COLORS) is True
    editor = SettingsEditor(AppSettings.default())
    renderer = ModalRenderer()
    key_codes = FakeModalKeyCodes()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=FakeWindow(),
    )
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        editor_provider=lambda: editor,
        modal_renderer=renderer,
        modal_key_codes=key_codes,
    )
    controls = renderer.controls(renderer.view_model(dialogs, editor), width=960, height=640)
    body = next(
        control
        for control in controls
        if control.action.value == "edit_field" and control.target == "color.body"
    )

    assert application.on_mouse_press(int(body.x + 1), int(body.y + 1), 1, 0) is True
    assert application.on_text("#ABCDEF") is True
    assert application._text_edit_target == "color.body"
    assert application._text_edit_buffer == "#ABCDEF"
    assert application.on_key_press(key_codes.ENTER, 0) is True
    assert editor.draft.controller_colors.body == "#ABCDEF"


def test_application_close_and_ctrl_q_submit_one_window_state_snapshot() -> None:
    key_codes = FakeModalKeyCodes()
    window = FakeWindow(width=1200, height=800)
    snapshots: list[object] = []
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=window,
    )
    application = PygletApplication(
        window=window,
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        settings_provider=AppSettings.default,
        modal_key_codes=key_codes,
        on_shutdown_requested=snapshots.append,
    )
    application.on_maximize()

    assert application.on_key_press(key_codes.Q, key_codes.MOD_CTRL) is True
    application.on_close()

    assert window.close_calls == 1
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert isinstance(snapshot, WindowSettings)
    assert snapshot.width == 1200
    assert snapshot.height == 800
    assert snapshot.maximized is True


def test_application_honors_saved_local_actions_before_controller_mapping() -> None:
    key_codes = FakeModalKeyCodes()
    settings = replace(
        AppSettings.default(),
        local_actions=LocalActions(
            toggle_capture=("CTRL+K",),
            quit=("CTRL+Q",),
            release_capture=("CTRL+K",),
        ),
    )
    window = FakeWindow()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=FakeSink()),
        window=window,
    )
    actions = FakeActions()
    application = PygletApplication(
        window=window,
        coordinator=coordinator,
        backend=PygletInputBackend(coordinator, key_codes=key_codes),
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        settings_provider=lambda: settings,
        modal_key_codes=key_codes,
        actions=actions,
    )
    assert coordinator.start_capture() is True

    assert application.on_key_press(key_codes.K, key_codes.MOD_CTRL) is True

    assert coordinator.is_captured is False
    assert actions.capture_toggles == 0
    assert coordinator.publisher.state.held_keys == set()


def test_application_modal_keyboard_isolation_preserves_f12_release() -> None:
    """Consume modal editing keys while leaving F12 for the input backend."""
    sink = FakeSink()
    key_codes = FakeModalKeyCodes()
    coordinator = CaptureCoordinator(
        publisher=InputPublisher(clock=FakeClock(), sink=sink),
        window=FakeWindow(),
    )
    assert coordinator.start_capture() is True
    dialogs = DialogManager()
    assert dialogs.open(DialogKind.MAPPING) is True
    backend = PygletInputBackend(coordinator, key_codes=key_codes)
    actions = FakeActions()
    application = PygletApplication(
        window=FakeWindow(),
        coordinator=coordinator,
        backend=backend,
        view=ControllerView(),
        toolbar=Toolbar(),
        status_bar=StatusBar(),
        dialogs=dialogs,
        actions=actions,
        modal_key_codes=key_codes,
    )

    assert application.on_key_press(key_codes.ESCAPE, 0) is True
    assert application.on_key_press(key_codes.ENTER, 0) is True
    assert application.on_key_press(key_codes.SPACE, 0) is True
    assert application.on_key_press(key_codes.TAB, 0) is True
    assert application.on_key_press(key_codes.F, 0) is True
    assert application.on_key_release(key_codes.F, 0) is True
    assert application.on_text("f") is True
    assert actions.cancels == 1
    assert actions.saves == 2

    assert application.on_key_press(key_codes.F12, 0) is None
    assert backend.on_key_press(key_codes.F12, 0) is True
    assert coordinator.is_captured is False
    assert application.on_key_release(key_codes.F12, 0) is None
    assert backend.on_key_release(key_codes.F12, 0) is True
