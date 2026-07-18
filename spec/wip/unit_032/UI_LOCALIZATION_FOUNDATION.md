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
| todo | 言語項目のない既存 schema v1 は英語を補完し、英語・日本語の明示値を TOML 往復する | new / regression | unit | 既存設定を RECOVERED にしない |
| todo | 英語既定ではアプリ固有 Widget と Qt 標準ボタンが英語で表示される | new | integration | main、mapping、connection、colors の代表文言を確認する |
| todo | 日本語選択ではアプリ用と Qt 用 translator が Widget 作成前に入り、同じ画面内で言語が混在しない | new | integration | Save / Cancel と `QColorDialog` を含める |
| todo | 指定 catalog を読み込めない場合は英語 UI で起動し、安全な警告だけを記録する | edge | integration | 半分だけ日本語になる状態を拒否する |
| todo | 翻訳後も canonical binding、diagnostic level、TOML key は英語の永続値を維持する | regression | unit | 表示 adapter と domain 値を分離する |
| todo | sdist と wheel に日本語 catalog が入り、展開先から読み込める | new / regression | package | repo 相対 path に依存しない smoke test |

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
| `pyproject.toml` | modify | package resource の同梱 |
| `tests/unit/config/test_codec.py` | modify | UI 言語の互換読込と往復 |
| `tests/unit/ui/test_localization.py` | new | catalog 選択、fallback、永続値分離 |
| `tests/integration/ui/*` | modify | 英語既定と日本語代表画面 |
| `tests/unit/test_packaging.py` | modify | 翻訳 resource の配布確認 |
| `spec/initial/configuration.md` | modify | UI 言語設定 |
| `spec/initial/requirements.md` | modify | 英語既定と翻訳整合の受入条件 |
| `spec/initial/testing.md` | modify | locale / package test |
| `spec/initial/ui.md` | modify | 表示文言と Qt 翻訳方針 |
| `spec/wip/unit_032/UI_LOCALIZATION_FOUNDATION.md` | new | 作業境界と検証記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_documentation.py tests/unit/test_work_unit_records.py` | pass | 3 passed、仕様作成時の文書構造を確認 |
| `uv run pytest tests/unit/config/test_codec.py tests/unit/ui/test_localization.py tests/integration/ui` | not run | 実装前の仕様作成段階 |
| `uv lock --check` / `uv build` | not run | package resource 追加時に必須 |
| 標準 gate | not run | 実装開始後に実行する |
| `$inspect-gui-states` による英語・日本語代表画面確認 | not run | 通常 Windows 描画で言語混在を確認する |

## 10. 先送り事項

- 実行中の言語切替と GUI 上の言語選択は、英語・日本語 catalog の package smoke 完了後に別 unit で扱う。
- 第3言語は翻訳提供者と受入環境が決まった時点で追加する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [x] 実装検証が未実行である理由を記録した
- [x] package resource 変更に `uv lock --check` と `uv build` を含めた
- [ ] 全 TDD Test List を green にした
- [ ] 初期仕様と翻訳 catalog を更新した
- [ ] 英語・日本語の実 GUI を確認した
