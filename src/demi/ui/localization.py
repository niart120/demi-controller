"""Process-wide Qt translation loading for the desktop user interface."""

from importlib.resources import as_file, files

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

from demi.domain.settings import UiLanguage


def install_translators(
    application: QApplication,
    language: UiLanguage,
) -> tuple[QTranslator, ...]:
    """Install matching application and Qt translators atomically.

    Args:
        application: Process-wide Qt application receiving translators.
        language: Validated user interface language.

    Returns:
        Installed translators whose lifetime must match the application runner.
        English and incomplete translation pairs return an empty tuple.
    """
    if language is UiLanguage.ENGLISH:
        return ()

    app_translator = QTranslator()
    catalog = files("demi.i18n").joinpath("demi_ja.qm")
    with as_file(catalog) as catalog_path:
        app_loaded = app_translator.load(str(catalog_path))

    qt_translator = QTranslator()
    qt_loaded = qt_translator.load(
        "qtbase_ja",
        QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath),
    )
    if not app_loaded or not qt_loaded:
        return ()

    application.installTranslator(app_translator)
    application.installTranslator(qt_translator)
    return (app_translator, qt_translator)
