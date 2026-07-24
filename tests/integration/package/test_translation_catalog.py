from pathlib import Path

from PySide6.QtCore import QTranslator


def test_compiled_japanese_catalog_translates_controller_status_text() -> None:
    catalog = Path(__file__).parents[3] / "src" / "demi" / "i18n" / "demi_ja.qm"
    translator = QTranslator()

    assert translator.load(str(catalog))
    assert translator.translate("ControllerPreviewWidget", "Mouse input") == "マウス入力"
    assert translator.translate("ControllerPreviewWidget", "On") == "有効"
    assert translator.translate("ControllerPreviewWidget", "Off") == "無効"
