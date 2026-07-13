"""Display models and delayed pyglet rendering for settings dialogs."""

from dataclasses import dataclass, replace
from enum import StrEnum

from demi.application.dialogs import DialogKind, DialogManager
from demi.application.presentation import AdapterOption
from demi.application.settings_editor import SettingsEditor
from demi.domain.mapping import Binding, BindingTarget, is_button_target
from demi.domain.settings import AppSettings


class ModalAction(StrEnum):
    """Actions exposed by the settings modal control layout."""

    CANCEL = "cancel"
    SAVE = "save"
    CAPTURE_BINDING = "capture_binding"
    TOGGLE_BINDING_INVERSION = "toggle_binding_inversion"
    RESET_PROFILE = "reset_profile"
    EDIT_FIELD = "edit_field"
    SELECT_ADAPTER = "select_adapter"
    RESCAN_ADAPTERS = "rescan_adapters"
    REQUEST_PAIRING = "request_pairing"
    CANCEL_PAIRING = "cancel_pairing"
    CONFIRM_PAIRING = "confirm_pairing"
    DEFER_COLOR_RECONNECT = "defer_color_reconnect"
    REQUEST_COLOR_RECONNECT = "request_color_reconnect"
    PREVIOUS_PAGE = "previous_page"
    NEXT_PAGE = "next_page"


@dataclass(frozen=True, slots=True)
class ModalField:
    """One current settings value and its optional editing action."""

    key: str
    label: str
    value: str
    hint: str = ""
    action: ModalAction | None = None
    action_label: str = ""
    target: str | None = None
    secondary_action: ModalAction | None = None
    secondary_action_label: str = ""
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class DialogViewModel:
    """User-facing state needed by a pyglet dialog renderer."""

    kind: DialogKind
    title: str
    visible: bool
    save_enabled: bool
    warning: str
    fields: tuple[ModalField, ...] = ()
    instructions: tuple[str, ...] = ()
    color_reconnect_pending: bool = False
    color_reconnect_prompt: bool = False
    pairing_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ModalControl:
    """One positioned modal action with an enabled state."""

    action: ModalAction
    label: str
    enabled: bool
    x: float
    y: float
    width: float
    height: float
    target: str | None = None

    def contains(self, x: float, y: float) -> bool:
        """Return whether a logical window coordinate is inside this control."""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


class ModalRenderer:
    """Draw and hit-test one paged pyglet modal without import-time display use."""

    _FIELDS_PER_PAGE = 5

    def __init__(self) -> None:
        """Initialize a renderer with no current hit-test layout."""
        self._last_controls: tuple[ModalControl, ...] = ()
        self._page_index = 0
        self._page_signature: tuple[DialogKind, str, bool, tuple[str, ...]] | None = None

    def view_model(
        self,
        dialogs: DialogManager,
        editor: SettingsEditor | None = None,
        *,
        adapters: tuple[AdapterOption, ...] = (),
        color_reconnect_pending: bool = False,
        text_edit_target: str | None = None,
        text_edit_value: str = "",
    ) -> DialogViewModel:
        """Build the current display model without importing pyglet.

        Args:
            dialogs: Owner of the real settings modal state.
            editor: Active immutable-draft editor, if an editable modal is open.
            adapters: Safe adapter choices from the main-thread presentation state.
            color_reconnect_pending: Whether saved colors await an explicit reconnect.
            text_edit_target: Draft field receiving text input, if any.
            text_edit_value: Uncommitted text shown with a cursor in that field.
        """
        return build_dialog_view_model(
            dialogs,
            editor,
            adapters=adapters,
            color_reconnect_pending=color_reconnect_pending,
            text_edit_target=text_edit_target,
            text_edit_value=text_edit_value,
        )

    def fields_for_page(self, model: DialogViewModel) -> tuple[ModalField, ...]:
        """Return the deterministic slice of fields visible on the current page."""
        self._sync_page(model)
        start = self._page_index * self._FIELDS_PER_PAGE
        return model.fields[start : start + self._FIELDS_PER_PAGE]

    def controls(
        self,
        model: DialogViewModel,
        *,
        width: int,
        height: int,
    ) -> tuple[ModalControl, ...]:
        """Return action controls for the supplied dialog view model."""
        if not model.visible:
            self._last_controls = ()
            return self._last_controls
        panel_x, panel_y, panel_width, panel_height = self._panel_bounds(width, height)
        fields = self.fields_for_page(model)
        controls = list(
            self._field_controls(
                fields,
                model=model,
                panel_x=panel_x,
                panel_y=panel_y,
                panel_width=panel_width,
                panel_height=panel_height,
            )
        )
        controls.extend(
            self._pagination_controls(
                model,
                panel_x=panel_x,
                panel_y=panel_y,
            )
        )
        controls.extend(
            self._footer_controls(
                model,
                panel_x=panel_x,
                panel_y=panel_y,
                panel_width=panel_width,
            )
        )
        self._last_controls = tuple(controls)
        return self._last_controls

    def hit_test(self, x: float, y: float, *, width: int, height: int) -> ModalControl | None:
        """Return the enabled action at a logical coordinate from the last layout.

        Page navigation is renderer-local, so a navigation hit advances the
        next layout even before the application action port handles the click.
        """
        del width, height
        for control in self._last_controls:
            if control.enabled and control.contains(x, y):
                self.activate(control)
                return control
        return None

    def activate(self, control: ModalControl) -> None:
        """Apply a renderer-local control action when no settings mutation is needed."""
        if control.action is ModalAction.PREVIOUS_PAGE:
            self._page_index = max(0, self._page_index - 1)
        elif control.action is ModalAction.NEXT_PAGE:
            self._page_index += 1

    def draw(self, model: DialogViewModel, *, width: int, height: int) -> None:
        """Draw a modal panel, current values, instructions, and action controls.

        Args:
            model: Display-free dialog state from the application session.
            width: Logical window width in pixels.
            height: Logical window height in pixels.
        """
        if not model.visible:
            self._last_controls = ()
            return
        from pyglet import shapes  # noqa: PLC0415
        from pyglet.text import Label  # noqa: PLC0415

        panel_x, panel_y, panel_width, panel_height = self._panel_bounds(width, height)
        shapes.Rectangle(0, 0, width, height, color=(0, 0, 0)).draw()
        shapes.Rectangle(
            panel_x,
            panel_y,
            panel_width,
            panel_height,
            color=(42, 45, 52),
        ).draw()
        Label(model.title, x=panel_x + 24, y=panel_y + panel_height - 42).draw()

        instruction_y = panel_y + panel_height - 72.0
        for instruction in model.instructions:
            Label(instruction, x=panel_x + 24, y=instruction_y).draw()
            instruction_y -= 18.0

        for index, field in enumerate(self.fields_for_page(model)):
            row_y = self._field_row_y(
                index,
                model=model,
                panel_y=panel_y,
                panel_height=panel_height,
            )
            Label(field.label, x=panel_x + 24, y=row_y + 9).draw()
            Label(field.value, x=panel_x + 188, y=row_y + 9).draw()
            if field.hint:
                Label(field.hint, x=panel_x + 188, y=row_y - 7, color=(190, 190, 190, 255)).draw()

        if model.warning:
            Label(model.warning, x=panel_x + 24, y=panel_y + 72, color=(255, 190, 90, 255)).draw()
        page_count = self._page_count(model)
        if page_count > 1:
            Label(
                f"{self._page_index + 1}/{page_count}",
                x=panel_x + 278,
                y=panel_y + 30,
            ).draw()
        for control in self.controls(model, width=width, height=height):
            color = (50, 98, 150) if control.enabled else (75, 75, 75)
            shapes.Rectangle(
                control.x,
                control.y,
                control.width,
                control.height,
                color=color,
            ).draw()
            Label(control.label, x=control.x + 8, y=control.y + 8).draw()

    def _field_controls(
        self,
        fields: tuple[ModalField, ...],
        *,
        model: DialogViewModel,
        panel_x: float,
        panel_y: float,
        panel_width: float,
        panel_height: float,
    ) -> tuple[ModalControl, ...]:
        controls: list[ModalControl] = []
        for index, field in enumerate(fields):
            row_y = self._field_row_y(
                index,
                model=model,
                panel_y=panel_y,
                panel_height=panel_height,
            )
            if field.secondary_action is not None:
                controls.append(
                    ModalControl(
                        action=field.secondary_action,
                        label=field.secondary_action_label,
                        enabled=field.enabled,
                        target=field.target,
                        x=panel_x + panel_width - 158.0,
                        y=row_y,
                        width=66.0,
                        height=32.0,
                    )
                )
            if field.action is not None:
                controls.append(
                    ModalControl(
                        action=field.action,
                        label=field.action_label,
                        enabled=field.enabled,
                        target=field.target,
                        x=panel_x + panel_width - 84.0,
                        y=row_y,
                        width=72.0,
                        height=32.0,
                    )
                )
        return tuple(controls)

    def _pagination_controls(
        self,
        model: DialogViewModel,
        *,
        panel_x: float,
        panel_y: float,
    ) -> tuple[ModalControl, ...]:
        page_count = self._page_count(model)
        if page_count <= 1:
            return ()
        return (
            ModalControl(
                action=ModalAction.PREVIOUS_PAGE,
                label="前",
                enabled=self._page_index > 0,
                x=panel_x + 222.0,
                y=panel_y + 20.0,
                width=48.0,
                height=32.0,
            ),
            ModalControl(
                action=ModalAction.NEXT_PAGE,
                label="次",
                enabled=self._page_index < page_count - 1,
                x=panel_x + 330.0,
                y=panel_y + 20.0,
                width=48.0,
                height=32.0,
            ),
        )

    @staticmethod
    def _footer_controls(
        model: DialogViewModel,
        *,
        panel_x: float,
        panel_y: float,
        panel_width: float,
    ) -> tuple[ModalControl, ...]:
        if model.color_reconnect_prompt:
            return (
                ModalControl(
                    action=ModalAction.DEFER_COLOR_RECONNECT,
                    label="後で",
                    enabled=True,
                    x=panel_x + 24.0,
                    y=panel_y + 20.0,
                    width=80.0,
                    height=32.0,
                ),
                ModalControl(
                    action=ModalAction.REQUEST_COLOR_RECONNECT,
                    label="再接続して反映",
                    enabled=True,
                    x=panel_x + 112.0,
                    y=panel_y + 20.0,
                    width=136.0,
                    height=32.0,
                ),
            )

        controls: list[ModalControl] = []
        if model.kind is DialogKind.MAPPING:
            controls.append(
                ModalControl(
                    action=ModalAction.RESET_PROFILE,
                    label="標準へ戻す",
                    enabled=model.save_enabled,
                    x=panel_x + 24.0,
                    y=panel_y + 20.0,
                    width=112.0,
                    height=32.0,
                )
            )
        elif model.kind is DialogKind.CONNECTION:
            controls.extend(
                (
                    ModalControl(
                        action=ModalAction.RESCAN_ADAPTERS,
                        label="再検索",
                        enabled=model.save_enabled,
                        x=panel_x + 24.0,
                        y=panel_y + 20.0,
                        width=80.0,
                        height=32.0,
                    ),
                    ModalControl(
                        action=ModalAction.REQUEST_PAIRING,
                        label="新規ペアリング",
                        enabled=model.pairing_enabled,
                        x=panel_x + 112.0,
                        y=panel_y + 20.0,
                        width=120.0,
                        height=32.0,
                    ),
                )
            )

        if model.kind is DialogKind.PAIRING_CONFIRMATION:
            controls.extend(
                (
                    ModalControl(
                        action=ModalAction.CANCEL_PAIRING,
                        label="接続設定へ戻る",
                        enabled=True,
                        x=panel_x + panel_width - 244.0,
                        y=panel_y + 20.0,
                        width=132.0,
                        height=32.0,
                    ),
                    ModalControl(
                        action=ModalAction.CONFIRM_PAIRING,
                        label="ペアリング開始",
                        enabled=model.pairing_enabled,
                        x=panel_x + panel_width - 104.0,
                        y=panel_y + 20.0,
                        width=92.0,
                        height=32.0,
                    ),
                )
            )
            return tuple(controls)

        controls.append(
            ModalControl(
                action=ModalAction.CANCEL,
                label="取消",
                enabled=True,
                x=panel_x + panel_width - 204.0,
                y=panel_y + 20.0,
                width=88.0,
                height=32.0,
            )
        )
        if model.save_enabled:
            controls.append(
                ModalControl(
                    action=ModalAction.SAVE,
                    label="保存",
                    enabled=True,
                    x=panel_x + panel_width - 108.0,
                    y=panel_y + 20.0,
                    width=96.0,
                    height=32.0,
                )
            )
        return tuple(controls)

    @classmethod
    def _field_row_y(
        cls,
        index: int,
        *,
        model: DialogViewModel,
        panel_y: float,
        panel_height: float,
    ) -> float:
        return panel_y + panel_height - 108.0 - len(model.instructions) * 18.0 - index * 42.0

    def _page_count(self, model: DialogViewModel) -> int:
        return max(1, (len(model.fields) + self._FIELDS_PER_PAGE - 1) // self._FIELDS_PER_PAGE)

    def _sync_page(self, model: DialogViewModel) -> None:
        signature = (
            model.kind,
            model.title,
            model.color_reconnect_prompt,
            tuple(field.key for field in model.fields),
        )
        if signature != self._page_signature:
            self._page_signature = signature
            self._page_index = 0
        self._page_index = min(self._page_index, self._page_count(model) - 1)

    @staticmethod
    def _panel_bounds(width: int, height: int) -> tuple[float, float, float, float]:
        panel_width = min(float(width - 48), 720.0)
        panel_height = min(float(height - 72), 480.0)
        return (
            (width - panel_width) / 2.0,
            (height - panel_height) / 2.0,
            panel_width,
            panel_height,
        )


_TARGET_LABELS: dict[BindingTarget, str] = {
    BindingTarget.BUTTON_A: "A",
    BindingTarget.BUTTON_B: "B",
    BindingTarget.BUTTON_X: "X",
    BindingTarget.BUTTON_Y: "Y",
    BindingTarget.BUTTON_L: "L",
    BindingTarget.BUTTON_R: "R",
    BindingTarget.BUTTON_ZL: "ZL",
    BindingTarget.BUTTON_ZR: "ZR",
    BindingTarget.BUTTON_PLUS: "プラス",
    BindingTarget.BUTTON_MINUS: "マイナス",
    BindingTarget.BUTTON_HOME: "ホーム",
    BindingTarget.BUTTON_CAPTURE: "キャプチャー",
    BindingTarget.BUTTON_LEFT_STICK: "左スティック押下",
    BindingTarget.BUTTON_RIGHT_STICK: "右スティック押下",
    BindingTarget.BUTTON_DPAD_UP: "十字上",
    BindingTarget.BUTTON_DPAD_DOWN: "十字下",
    BindingTarget.BUTTON_DPAD_LEFT: "十字左",
    BindingTarget.BUTTON_DPAD_RIGHT: "十字右",
    BindingTarget.LEFT_STICK_UP: "左スティック上",
    BindingTarget.LEFT_STICK_DOWN: "左スティック下",
    BindingTarget.LEFT_STICK_LEFT: "左スティック左",
    BindingTarget.LEFT_STICK_RIGHT: "左スティック右",
    BindingTarget.RIGHT_STICK_UP: "右スティック上",
    BindingTarget.RIGHT_STICK_DOWN: "右スティック下",
    BindingTarget.RIGHT_STICK_LEFT: "右スティック左",
    BindingTarget.RIGHT_STICK_RIGHT: "右スティック右",
}


def build_dialog_view_model(
    dialogs: DialogManager,
    editor: SettingsEditor | None = None,
    *,
    adapters: tuple[AdapterOption, ...] = (),
    color_reconnect_pending: bool = False,
    text_edit_target: str | None = None,
    text_edit_value: str = "",
) -> DialogViewModel:
    """Build a dialog view model without importing pyglet or swbt.

    Args:
        dialogs: Owner of the currently active settings modal.
        editor: Immutable draft editor for the active settings modal.
        adapters: Safe adapter choices from discovery.
        color_reconnect_pending: Whether saved colors await an explicit reconnect.
        text_edit_target: Draft field receiving text input, if any.
        text_edit_value: Uncommitted text shown with a cursor in that field.
    """
    dialog = dialogs.model
    if dialog.kind is DialogKind.NONE and color_reconnect_pending:
        return DialogViewModel(
            kind=DialogKind.NONE,
            title="コントローラーカラーの再接続",
            visible=True,
            save_enabled=False,
            warning="再接続後も入力捕捉は自動で再開しません",
            instructions=(
                "表示色は更新済みです。",
                "対象機器へ反映するにはコントローラーを再接続します。",
            ),
            color_reconnect_pending=True,
            color_reconnect_prompt=True,
        )
    if not dialog.visible:
        return DialogViewModel(
            kind=dialog.kind,
            title=dialog.title,
            visible=False,
            save_enabled=False,
            warning="",
        )

    draft = editor.draft if editor is not None else None
    fields: tuple[ModalField, ...] = ()
    instructions: tuple[str, ...] = ()
    pairing_enabled = False
    warning = ""
    if dialog.kind is DialogKind.MAPPING and editor is not None:
        fields = _mapping_fields(editor.draft)
        instructions = (
            "変更で次のキーまたはマウス入力を取得します。",
            "F12 は入力捕捉解除として予約されています。",
        )
        conflict_count = len(editor.conflicts())
        warning = "" if conflict_count == 0 else f"割り当ての競合: {conflict_count}件"
    elif dialog.kind is DialogKind.CONNECTION and draft is not None:
        fields = _connection_fields(draft, adapters)
        instructions = ("USB アダプターを選んで保存済みボンドへ接続します。",)
        pairing_enabled = _can_pair(draft, adapters)
    elif dialog.kind is DialogKind.COLORS and draft is not None:
        fields = _color_fields(draft)
        instructions = ("#RRGGBB 形式で入力し、保存前に表示色を確認します。",)
    elif dialog.kind is DialogKind.PAIRING_CONFIRMATION:
        instructions = (
            "対象機器側でコントローラー登録画面を開いてください。",
            "専用 USB Bluetooth アダプターを接続してください。",
            "既存ボンドスロットは上書きされることがあります。",
            "処理中に USB アダプターを抜かないでください。",
        )
        if draft is None:
            pairing_enabled = True
        else:
            fields = _pairing_fields(draft, adapters)
            pairing_enabled = _can_pair(draft, adapters)

    if text_edit_target is not None:
        fields = tuple(
            replace(field, value=f"{text_edit_value}|") if field.key == text_edit_target else field
            for field in fields
        )

    return DialogViewModel(
        kind=dialog.kind,
        title=dialog.title,
        visible=True,
        save_enabled=editor is not None and dialog.kind is not DialogKind.PAIRING_CONFIRMATION,
        warning=warning,
        fields=fields,
        instructions=instructions,
        color_reconnect_pending=color_reconnect_pending,
        pairing_enabled=pairing_enabled,
    )


def _mapping_fields(settings: AppSettings) -> tuple[ModalField, ...]:
    profile = next(
        profile for profile in settings.profiles if profile.id == settings.active_profile
    )
    fields: list[ModalField] = [
        ModalField(
            key="profile",
            label="プロファイル",
            value=profile.name,
            hint="標準プロファイルを使用中" if profile.builtin else "保存済みプロファイル",
        )
    ]
    fields.extend(_binding_field(index, binding) for index, binding in enumerate(profile.bindings))
    mouse = settings.input.mouse
    fields.extend(
        (
            ModalField(
                key="mouse.gyro_enabled",
                label="マウスジャイロ",
                value="有効" if mouse.gyro_enabled else "無効",
                action=ModalAction.EDIT_FIELD,
                action_label="切替",
                target="mouse.gyro_enabled",
            ),
            ModalField(
                key="mouse.horizontal_sensitivity",
                label="水平感度",
                value=f"{mouse.horizontal_sensitivity:g} 倍",
                hint="0.1〜10.0",
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="mouse.horizontal_sensitivity",
            ),
            ModalField(
                key="mouse.vertical_sensitivity",
                label="垂直感度",
                value=f"{mouse.vertical_sensitivity:g} 倍",
                hint="0.1〜10.0",
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="mouse.vertical_sensitivity",
            ),
            ModalField(
                key="mouse.invert_y",
                label="Y 反転",
                value="有効" if mouse.invert_y else "無効",
                action=ModalAction.EDIT_FIELD,
                action_label="切替",
                target="mouse.invert_y",
            ),
            ModalField(
                key="mouse.pitch_limit_degrees",
                label="pitch 上限",
                value=f"{mouse.pitch_limit_degrees:g} 度",
                hint="1〜89 度",
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="mouse.pitch_limit_degrees",
            ),
            ModalField(
                key="input.circular_stick_limit",
                label="円形スティック制限",
                value="有効" if settings.input.circular_stick_limit else "無効",
                action=ModalAction.EDIT_FIELD,
                action_label="切替",
                target="input.circular_stick_limit",
            ),
            ModalField(
                key="input.evaluation_interval_ms",
                label="入力評価間隔",
                value=f"{settings.input.evaluation_interval_ms} ms",
                hint="4〜32 ms",
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="input.evaluation_interval_ms",
            ),
        )
    )
    return tuple(fields)


def _binding_field(index: int, binding: Binding) -> ModalField:
    """Build one editable binding row from a validated binding."""
    return ModalField(
        key=f"binding.{index}",
        label=_TARGET_LABELS[binding.target],
        value=f"{binding.source}{' (反転)' if binding.inverted else ''}",
        action=ModalAction.CAPTURE_BINDING,
        action_label="変更",
        target=str(index),
        secondary_action=(
            ModalAction.TOGGLE_BINDING_INVERSION if is_button_target(binding.target) else None
        ),
        secondary_action_label="反転" if is_button_target(binding.target) else "",
    )


def _connection_fields(
    settings: AppSettings,
    adapters: tuple[AdapterOption, ...],
) -> tuple[ModalField, ...]:
    connection = settings.connection
    fields: list[ModalField] = [
        ModalField(
            key="connection.adapter_id",
            label="USB アダプター",
            value=_adapter_selection_label(connection.adapter_id, adapters),
        )
    ]
    fields.extend(
        ModalField(
            key=f"adapter.{adapter.id}",
            label=adapter.label,
            value=adapter.id,
            action=ModalAction.SELECT_ADAPTER,
            action_label="選択中" if adapter.id == connection.adapter_id else "選択",
            target=adapter.id,
            enabled=adapter.id != connection.adapter_id,
        )
        for adapter in adapters
    )
    fields.extend(
        (
            ModalField(
                key="connection.controller",
                label="コントローラー",
                value="Pro Controller",
                hint="0.1.0 では固定です",
                enabled=False,
            ),
            ModalField(
                key="connection.bond_slot",
                label="ボンドスロット",
                value=connection.bond_slot,
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="connection.bond_slot",
            ),
            ModalField(
                key="connection.timeout_seconds",
                label="接続タイムアウト",
                value=f"{connection.timeout_seconds:g} 秒",
                hint="1〜120 秒",
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="connection.timeout_seconds",
            ),
            ModalField(
                key="connection.reconnect_on_start",
                label="起動時の再接続",
                value="有効" if connection.reconnect_on_start else "無効",
                action=ModalAction.EDIT_FIELD,
                action_label="切替",
                target="connection.reconnect_on_start",
            ),
            ModalField(
                key="connection.diagnostic_level",
                label="診断ログ",
                value=connection.diagnostic_level.value,
                action=ModalAction.EDIT_FIELD,
                action_label="変更",
                target="connection.diagnostic_level",
            ),
        )
    )
    return tuple(fields)


def _color_fields(settings: AppSettings) -> tuple[ModalField, ...]:
    colors = settings.controller_colors
    return (
        ModalField(
            key="color.body",
            label="本体",
            value=colors.body,
            action=ModalAction.EDIT_FIELD,
            action_label="変更",
            target="color.body",
        ),
        ModalField(
            key="color.buttons",
            label="ボタン",
            value=colors.buttons,
            action=ModalAction.EDIT_FIELD,
            action_label="変更",
            target="color.buttons",
        ),
        ModalField(
            key="color.left_grip",
            label="左グリップ",
            value=colors.left_grip,
            action=ModalAction.EDIT_FIELD,
            action_label="変更",
            target="color.left_grip",
        ),
        ModalField(
            key="color.right_grip",
            label="右グリップ",
            value=colors.right_grip,
            action=ModalAction.EDIT_FIELD,
            action_label="変更",
            target="color.right_grip",
        ),
    )


def _pairing_fields(
    settings: AppSettings,
    adapters: tuple[AdapterOption, ...],
) -> tuple[ModalField, ...]:
    connection = settings.connection
    return (
        ModalField(
            key="connection.adapter_id",
            label="対象 USB アダプター",
            value=_adapter_selection_label(connection.adapter_id, adapters),
        ),
        ModalField(
            key="connection.bond_slot",
            label="上書きするボンドスロット",
            value=connection.bond_slot,
        ),
        ModalField(
            key="connection.timeout_seconds",
            label="接続タイムアウト",
            value=f"{connection.timeout_seconds:g} 秒",
        ),
    )


def _adapter_selection_label(adapter_id: str, adapters: tuple[AdapterOption, ...]) -> str:
    if not adapter_id:
        return "未選択"
    for adapter in adapters:
        if adapter.id == adapter_id:
            return f"{adapter.label} ({adapter.id})"
    return f"{adapter_id} (検出待ち)"


def _can_pair(settings: AppSettings, adapters: tuple[AdapterOption, ...]) -> bool:
    adapter_id = settings.connection.adapter_id
    return bool(adapter_id) and any(adapter.id == adapter_id for adapter in adapters)
