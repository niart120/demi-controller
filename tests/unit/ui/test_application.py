from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from demi.app import ApplicationDependencies, WindowSpec
from demi.domain.settings import WindowSettings
from demi.ui.application import QtApplicationRunner
from demi.ui.main_window import MainWindow
from demi.ui.status_bar import MainStatusBar
from demi.ui.toolbar import MainToolBar


def test_runner_reuses_the_process_qapplication(qt_application: object) -> None:
    runner = QtApplicationRunner()

    assert runner.application is qt_application


def test_default_dependencies_create_the_qt_runner_and_main_window(
    qt_application: object,
) -> None:
    dependencies = ApplicationDependencies.default()

    window = dependencies.window_factory(WindowSpec(width=960, height=640, maximized=False))
    gui = dependencies.gui_factory(
        window=window,
        on_shutdown_requested=lambda _state: True,
    )

    assert isinstance(window, MainWindow)
    assert isinstance(gui, QtApplicationRunner)
    assert gui.application is qt_application
    window.close()


def test_offscreen_fixture_reuses_the_application_and_cleans_top_level_windows(
    qt_application: QApplication,
    qt_top_level_window_cleanup: Callable[[QApplication], None],
) -> None:
    first_runner = QtApplicationRunner()
    second_runner = QtApplicationRunner()
    window = first_runner.create_main_window(WindowSpec(width=960, height=640, maximized=False))
    window.show()

    qt_top_level_window_cleanup(qt_application)

    assert first_runner.application is qt_application
    assert second_runner.application is qt_application
    assert qt_application.topLevelWidgets() == []


def test_runner_creates_a_resizable_main_window(qt_application: object) -> None:
    runner = QtApplicationRunner()

    window = runner.create_main_window(WindowSpec(width=960, height=640, maximized=False))

    assert runner.application is qt_application
    assert (window.width(), window.height()) == (960, 640)
    assert (window.minimumWidth(), window.minimumHeight()) == (800, 520)
    assert window.centralWidget() is not None

    window.resize(1024, 768)

    assert (window.width(), window.height()) == (1024, 768)
    window.close()


def test_main_window_uses_standard_toolbar_and_status_bar(qt_application: object) -> None:
    assert qt_application is not None
    window = MainWindow(WindowSpec(width=960, height=640, maximized=False))

    assert isinstance(window.main_toolbar, MainToolBar)
    assert window.toolBarArea(window.main_toolbar) is Qt.ToolBarArea.TopToolBarArea
    assert isinstance(window.status_bar, MainStatusBar)
    assert window.statusBar() is window.status_bar
    assert window.centralWidget() is window.controller_preview


def test_main_window_restores_and_saves_window_state(qt_application: object) -> None:
    runner = QtApplicationRunner()

    window = runner.create_main_window(WindowSpec(width=1200, height=800, maximized=True))

    assert runner.application is qt_application
    assert window.isMaximized() is True
    assert window.window_state() == WindowSettings(width=1200, height=800, maximized=True)

    window.showNormal()
    window.resize(1100, 700)

    assert window.window_state() == WindowSettings(width=1100, height=700, maximized=False)
    window.close()


def test_main_window_routes_close_and_quit_to_one_shutdown_callback(
    qt_application: object,
) -> None:
    runner = QtApplicationRunner()
    close_window = runner.create_main_window(WindowSpec(width=960, height=640, maximized=False))
    close_states: list[WindowSettings | None] = []

    def request_close(state: WindowSettings | None) -> bool:
        close_states.append(state)
        return True

    close_window.set_shutdown_callback(request_close)
    close_event = QCloseEvent()
    close_event.ignore()
    close_window.closeEvent(close_event)
    duplicate_event = QCloseEvent()
    duplicate_event.ignore()
    close_window.closeEvent(duplicate_event)

    assert runner.application is qt_application
    assert close_states == [WindowSettings(width=960, height=640, maximized=False)]
    assert close_event.isAccepted() is True
    assert duplicate_event.isAccepted() is True

    shortcut_window = runner.create_main_window(WindowSpec(width=960, height=640, maximized=False))
    shortcut_states: list[WindowSettings | None] = []
    shortcut_window.set_shutdown_callback(lambda state: shortcut_states.append(state) or True)

    shortcut_window.quit_action.trigger()

    assert shortcut_states == [WindowSettings(width=960, height=640, maximized=False)]
