from demi.app import WindowSpec
from demi.ui.application import QtApplicationRunner


def test_runner_reuses_the_process_qapplication(qt_application: object) -> None:
    runner = QtApplicationRunner()

    assert runner.application is qt_application


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
