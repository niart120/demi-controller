"""Display-free presentation models for settings dialogs."""

from dataclasses import dataclass

from demi.application.dialogs import DialogKind, DialogManager
from demi.application.settings_editor import SettingsEditor


@dataclass(frozen=True, slots=True)
class DialogViewModel:
    """User-facing state needed by a pyglet dialog renderer."""

    kind: DialogKind
    title: str
    visible: bool
    save_enabled: bool
    warning: str


def build_dialog_view_model(
    dialogs: DialogManager,
    editor: SettingsEditor | None = None,
) -> DialogViewModel:
    """Build a dialog view model without importing pyglet or swbt."""
    model = dialogs.model
    conflict_count = 0 if editor is None else len(editor.conflicts())
    warning = "" if conflict_count == 0 else f"割り当ての競合: {conflict_count}件"
    return DialogViewModel(
        kind=model.kind,
        title=model.title,
        visible=model.visible,
        save_enabled=model.visible and editor is not None,
        warning=warning,
    )
