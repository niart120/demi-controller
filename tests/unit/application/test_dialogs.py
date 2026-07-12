from demi.application.dialogs import DialogKind, DialogManager


def test_dialog_manager_allows_one_modal_and_exposes_user_titles() -> None:
    manager = DialogManager()

    assert manager.model.kind is DialogKind.NONE
    assert manager.open(DialogKind.MAPPING) is True
    assert manager.model.title == "キー割り当て"
    assert manager.open(DialogKind.CONNECTION) is False
    assert manager.model.kind is DialogKind.MAPPING

    manager.close()

    assert manager.open(DialogKind.COLORS) is True
    assert manager.model.title == "コントローラーカラー"
    assert manager.open(DialogKind.PAIRING_CONFIRMATION) is False


def test_dialog_manager_close_is_idempotent_and_pairing_has_confirmation_title() -> None:
    manager = DialogManager()

    manager.close()
    assert manager.open(DialogKind.PAIRING_CONFIRMATION) is True
    assert manager.model.title == "新規ペアリングの確認"
    manager.close()
    manager.close()
    assert manager.model.kind is DialogKind.NONE
