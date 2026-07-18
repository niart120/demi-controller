# 英語既定の UI 多言語基盤 仕様書

## 1. 概要

### 1.1 目的

UI の既定言語を英語に統一し、アプリ固有文言と Qt 標準ダイアログを同じ言語設定で翻訳できる基盤を追加する。日本語は選択可能な翻訳として提供し、翻訳資源がない場合は英語へ安全に戻す。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | 日本語固定ではなく、既定を英語として日本語化できる拡張を加える | 対話、2026-07-19 |
| GUI review | アプリ文言は日本語、`QDialogButtonBox` と `QColorDialog` は英語となり、1画面内で言語が混在した | `src/demi/ui` |
| current settings | UI 言語設定と `QTranslator` の起動境界が存在しない | `src/demi/domain/settings.py`, `src/demi/ui/application.py` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| new user | 言語指定のない設定で起動する | アプリ固有文言と Qt 標準ボタンを英語で表示する | OS locale から日本語へ自動変更しない |
| Japanese user | `ui.language = "ja"` で起動する | アプリ文言、Save / Cancel、標準色選択を日本語で表示する | Widget 生成前に translator を設定する |
| application | 指定言語の翻訳資源を読み込めない | 起動を継続し、英語表示と安全な警告記録へ戻る | 一部だけ別言語にしない |
| existing user | UI 言語項目のない schema v1 を読み込む | `en` を補完し、既存設定を保持する | 破損復旧扱いにしない |

## 2. 対象範囲

- `UiLanguage` と UI 言語設定を追加し、既定値を `en` とする。
- schema v1 の UI 言語欠落を `en` で補完し、`en` / `ja` を TOML 往復する。
- source 上の利用者向け文言を英語の翻訳元へ統一し、`QObject.tr()` または `QCoreApplication.translate()` を通す。
- アプリ用翻訳 catalog と Qt 標準翻訳を、main window 作成前に同じ言語で読み込む。
- 日本語 catalog を package resource として同梱し、wheel / sdist から読み込めるようにする。
- toolbar、status bar、mapping、connection、pairing、colors、通知・安全な error 文言を翻訳対象にする。
- 翻訳済み表示と、設定・ログ・domain enum の永続値を分離する。
- `spec/initial/configuration.md`、`spec/initial/ui.md`、`spec/initial/testing.md` の言語契約を更新する。

## 3. 対象外

- 実行中の即時言語切替。設定変更後の再起動を必要とする。
- 言語選択専用ダイアログ。初回は設定値と起動境界を提供する。
- OS locale に追従する `system` モード。
- ログ、TOML key、canonical binding、diagnostic enum の翻訳。
- 英語・日本語以外の翻訳完成。ただし catalog 追加で拡張できる構造にする。
- 翻訳サービス、ネットワーク取得、外部 i18n runtime dependency。

## 4. 関連 docs

- `spec/initial/configuration.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/ui.md`
- `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md`
- `spec/complete/unit_014/PYSIDE6_APPLICATION_SHELL.md`
- `spec/complete/unit_016/QT_STANDARD_CONTROLS_AND_DIALOGS.md`
- `spec/wip/unit_034/CONTROLLER_PREVIEW_VISUALIZATION.md`
- `spec/wip/unit_035/INLINE_KEY_MAPPING.md`
- `spec/wip/unit_036/COLOR_SWATCH_BUTTONS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| 英語で起動する | UI 言語が欠落または `en` | translator なしでも英語の完全な UI になる | 英語を source text とする |
| 日本語で起動する | UI 言語が `ja` | app catalog と Qt catalog の両方を Widget 作成前に install する | runner が translator の lifetime を所有する |
| catalog 不足へ戻る | `ja` catalog または Qt catalog を読み込めない | app / Qt の translator を中途半端に install せず英語へ戻る | safe warning をログへ残す |
| 設定を移行する | UI table のない schema v1 | `language = "en"` を補完し、他の設定を変えない | schema identity は維持する |
| 表示と永続値を分ける | 日本語 UI で設定を保存 | `INFO`、`KEY:F` などの canonical 値は翻訳前の値で保存する | 表示 model だけを翻訳する |
| 配布物から翻訳する | wheel を展開して日本語起動 | filesystem 上の repo に依存せず catalog を読み込む | package resource API を使う |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | 言語項目のない既存 schema v1 は英語を補完し、英語・日本語の明示値を TOML 往復する | new / regression | unit | 24 tests green。責務重複がないため構造変更なし |
| refactor-skipped | 英語既定ではアプリ固有 Widget と Qt 標準ボタンが英語で表示される | new | integration | 18 tests green。既存 Widget 境界を維持したため構造変更なし |
| refactor-skipped | 日本語選択ではアプリ用と Qt 用 translator が Widget 作成前に入り、同じ画面内で言語が混在しない | new | integration | 26 tests green。translator 所有境界を新設済みで追加の構造変更なし |
| refactor-skipped | 指定 catalog を読み込めない場合は英語 UI で起動し、安全な警告だけを記録する | edge | integration | 3 tests green。既存の translator 境界に警告を追加したため構造変更なし |
| refactor-skipped | 翻訳後も canonical binding、diagnostic level、TOML key は英語の永続値を維持する | regression | unit | 20 tests green。model の表示変換だけを変更し domain / codec 構造は維持 |
| refactor-skipped | sdist と wheel に日本語 catalog が入り、展開先から読み込める | new / regression | package | smoke test green。uv-build の既定 package data 同梱で成立し、構造変更なし |
| refactor-skipped | 残存する利用者向け日本語直書きを英語 source text と catalog に移し、英語既定画面から日本語固定文言を除く | regression | unit / integration | unit 253件、UI integration 71件 green。Qt context ごとの翻訳境界を維持したため追加の構造変更なし |
| refactor-skipped | 日本語の割り当て画面で `Pitch limit` を `ピッチ上限` と表示し、1ラベル内の言語混在を除く | regression | integration / visual | GUI画像で `pitch上限` を確認してred化。catalog修正だけで既存境界を維持したため構造変更なし |

## 7. 設計メモ

英語を source text とし、日本語を catalog へ置く。独自辞書で Qt 標準部品を再実装せず、`QTranslator` を application process 境界で所有する。設定は application 起動後ではなく window factory 呼出し前に読めているため、読み込んだ `AppSettings` から UI 言語を runner 作成へ渡す。

後続の UI unit は新しい文言を英語 source text として追加し、日本語 catalog を同じ変更で更新する。翻訳漏れを実行時に推測で補わない。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `src/demi/domain/settings.py` | modify | UI 言語設定と英語既定値 |
| `src/demi/config/codec.py` | modify | schema v1 補完と TOML 往復 |
| `src/demi/app.py` | modify | 設定読込後、window 作成前の言語引き渡し |
| `src/demi/ui/localization.py` | new | app / Qt translator の一括読込と fallback |
| `src/demi/ui/application.py` | modify | translator lifetime と Widget 作成順 |
| `src/demi/ui/**/*.py` | modify | 利用者向け英語 source text と翻訳境界 |
| `src/demi/i18n/*` | new | 日本語 source catalog と配布用 catalog |
| `pyproject.toml` | inspect | `uv-build`の既定package data同梱で成立することを確認 |
| `tests/unit/config/test_codec.py` | modify | UI 言語の互換読込と往復 |
| `tests/unit/ui/test_localization.py` | new | catalog 選択、fallback、永続値分離 |
| `tests/integration/ui/*` | modify | 英語既定と日本語代表画面 |
| `tests/integration/package/test_translation_catalog.py` | new | 翻訳resourceの配布と展開wheelからの読込確認 |
| `spec/initial/configuration.md` | modify | UI 言語設定 |
| `spec/initial/requirements.md` | modify | 英語既定と翻訳整合の受入条件 |
| `spec/initial/testing.md` | modify | locale / package test |
| `spec/initial/ui.md` | modify | 表示文言と Qt 翻訳方針 |
| `spec/wip/unit_032/UI_LOCALIZATION_FOUNDATION.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest tests/unit/config/test_codec.py tests/unit/domain/test_settings.py -q` | pass | 24 passed。UI 言語欠落時の英語補完と `en` / `ja` の往復を確認 |
| `uv run ruff check src/demi/domain/settings.py src/demi/config/codec.py tests/unit/config/test_codec.py` | pass | 当該 cycle の変更範囲に指摘なし |
| `uv run ty check --no-progress` | pass | 型エラーなし |
| `uv run pytest tests/unit/ui/test_toolbar.py tests/unit/ui/test_mapping_model.py tests/integration/ui/test_toolbar_actions.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_connection_dialog.py tests/integration/ui/test_colors_dialog.py tests/integration/ui/test_localization.py -q` | pass | 18 passed。main toolbar、mapping、connection、colors と Qt 標準 Save / Cancel の英語表示を確認 |
| `uv run ruff check src/demi/ui/toolbar.py src/demi/ui/dialogs/mapping.py src/demi/ui/dialogs/connection.py src/demi/ui/dialogs/colors.py tests/unit/ui/test_toolbar.py tests/integration/ui/test_localization.py` | pass | 英語既定 UI cycle の変更範囲に指摘なし |
| `uv run pytest -p no:cacheprovider tests/integration/ui/test_localization.py tests/unit/ui/test_application.py tests/unit/application/test_app.py -q` | pass | 26 passed。日本語 app catalog、Qt 標準 Save / Cancel、`QColorDialog`、Widget 作成前の言語引き渡しを確認 |
| `uv run ruff check src/demi/app.py src/demi/ui/application.py src/demi/ui/localization.py src/demi/ui/toolbar.py src/demi/ui/dialogs/mapping.py src/demi/ui/dialogs/connection.py src/demi/ui/dialogs/colors.py src/demi/i18n tests/integration/ui/test_localization.py` | pass | translator cycle の変更範囲に指摘なし |
| `uv run pytest -p no:cacheprovider tests/unit/ui/test_localization_fallback.py tests/integration/ui/test_localization.py -q` | pass | 3 passed。app catalog 欠落時に translator を部分適用せず、英語 UI と安全な警告へ戻ることを確認 |
| `uv run ruff check src/demi/ui/localization.py tests/unit/ui/test_localization_fallback.py tests/integration/ui/test_localization.py` | pass | fallback cycle の変更範囲に指摘なし |
| `uv run pytest -p no:cacheprovider tests/unit/config/test_codec.py tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_localization.py -q` | pass | 20 passed。Yes / No の翻訳後も `KEY:F`、`BUTTON:A`、`INFO` と TOML key が canonical 値を維持 |
| `uv run ruff check src/demi/ui/dialogs/mapping.py tests/unit/ui/test_mapping_model.py tests/integration/ui/test_mapping_dialog.py tests/integration/ui/test_localization.py` | pass | canonical 値分離 cycle の変更範囲に指摘なし |
| `uv run pytest -p no:cacheprovider tests/unit -q` | pass | 253 passed。application の safe message と全 unit 回帰を確認 |
| `uv run pytest -p no:cacheprovider tests/integration/ui -q` | pass | 71 passed。英語既定 UI と日本語 catalog の GUI 回帰を確認 |
| `uv run pytest -p no:cacheprovider tests/unit/ui/test_english_source_text.py tests/integration/ui/test_localization.py -q` | pass | 3 passed。app / UI の日本語 source literal が0件で、英語・日本語の代表表示が一致 |
| `.venv\\Scripts\\pyside6-lrelease.exe src\\demi\\i18n\\demi_ja.ts -qm src\\demi\\i18n\\demi_ja.qm` | pass | 110件すべて finished、unfinished 0件 |
| `uv run pytest -p no:cacheprovider tests/integration/package/test_translation_catalog.py -q` | pass | 1 passed。sdist / wheel の `.ts` / `.qm` と、展開 wheel からの `importlib.resources` / `QTranslator.load()` を確認 |
| `uv run pytest -p no:cacheprovider tests/integration/ui/test_localization.py -q` | pass | 2 passed。画像で見つけた `pitch上限` を再現する失敗を確認後、`ピッチ上限` への修正を確認 |
| `$inspect-gui-states` による英語・日本語代表画面確認 | pass | 通常 Windows 描画で各言語の主画面と割り当て画面を取得。toolbar、status bar、mapping見出し、Qt標準 Save / Cancel に言語混在、切れ、重なりなし。修正後画像で `ピッチ上限` を確認 |
| `uv sync --dev` | pass | 77 packagesを解決し、74 packagesを確認 |
| `uv lock --check` | pass | lock差分なし |
| `uv run ruff format --check .` | pass | 141 files already formatted |
| `uv run ruff check .` | pass | 指摘なし |
| `uv run ty check --no-progress` | pass | 型エラーなし。追加の`Any`、ignore、互換用型依存なし |
| `uv run pytest -p no:cacheprovider tests/unit -q` | pass | 253 passed |
| `uv run pytest -p no:cacheprovider tests/integration -q` | pass | 83 passed |
| `uv build` | pass | sdistとwheelを生成 |
| `git diff --check` | pass | whitespace errorなし |
| `$docs-quality-review` | pass | 初期仕様4文書と作業仕様に仮テキスト、会話依存語、未実行の完了表現なし |

## 10. 先送り事項

- 実行中の言語切替と GUI 上の言語選択は、英語・日本語 catalog の package smoke 完了後に別 unit で扱う。
- 第3言語は翻訳提供者と受入環境が決まった時点で追加する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 実装検証が未実行である理由を記録した
- [x] package resource 変更に `uv lock --check` と `uv build` を含めた
- [x] 全 TDD Test List を green にした
- [x] 初期仕様と翻訳 catalog を更新した
- [x] 英語・日本語の実 GUI を確認した
