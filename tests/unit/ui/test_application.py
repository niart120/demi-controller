from demi.ui.application import QtApplicationRunner


def test_runner_reuses_the_process_qapplication(qt_application: object) -> None:
    runner = QtApplicationRunner()

    assert runner.application is qt_application
