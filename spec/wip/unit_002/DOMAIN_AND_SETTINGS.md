# ドメイン型と設定 仕様書

## 1. 概要

### 1.1 目的

ControllerFrame とその物理量、入力 binding、Default profile、AppSettings を不変のドメイン値として定義し、設定を検証済み TOML として安全に読み書きできる状態にする。Unit 003 以降は、この unit の値オブジェクトと設定契約を入力状態、UI、接続 runtime の共通境界として使う。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | Unit 002 の成果と完了条件 | `spec/initial/roadmap.md` |
| domain architecture | ControllerFrame、LogicalButton、物理量、依存方向 | `spec/initial/architecture.md` |
| configuration design | TOML schema、制約、読み込み、原子的保存、移行 | `spec/initial/configuration.md` |
| requirements | FR-013 設定保存、NFR-005/NFR-006 | `spec/initial/requirements.md` |
| test design | domain、設定、破損、移行の試験候補 | `spec/initial/testing.md` |
| project guide | Python、uv、型、検証 gate | `AGENTS.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| domain caller | finite なボタン、スティック、角速度、加速度の値 | 不変で検証済みのドメイン値を得る | `demi.domain` は標準ライブラリだけを import する |
| input mapper | 正規化された binding と物理入力 | Default profile と反転属性を失わず読み取れる | pyglet 型は持ち込まない |
| application startup | 設定ファイルが存在しない | Default settings と FIRST_RUN の結果を得る | 設定保存先は OS 固有パスへ固定しない |
| application startup | 現行 schema の TOML | AppSettings と LOADED の結果を得る | 未知の項目は実行時機能へ反映しない |
| application startup | 構文または意味が破損した TOML | 元ファイルを残し、日時付き backup と Default settings を得る | 元ファイルの上書き禁止 |
| settings caller | 有効な AppSettings | 同一ファイルシステム内の一時ファイルから原子的に置換する | UTF-8、LF、可能な範囲で flush/fsync |

## 2. 対象範囲

- `LogicalButton`、`StickVector`、`GyroRate`、`AccelG`、`ControllerFrame`。
- 物理入力名、論理ターゲット、binding、profile の設定値表現。
- `AppSettings` と window、connection、colors、mouse、local actions の既定値。
- Default profile の全 binding と `inverted` の検証。
- TOML codec、現行 schema 検証、未知 schema の拒否、移行フック。
- `platformdirs.PlatformDirs(appname="Project_Demi", appauthor=False)` によるパス解決。
- 初回読み込み、正常読み込み、原子的保存、破損ファイルの日時付き退避。
- `platformdirs`、`tomli-w` の依存追加と package gate。

## 3. 対象外

- pyglet のキー・マウスイベント、PhysicalInputState の更新、InputMapper の評価。
- YawPitchModel、8ms publisher、GUI 設定モーダル。
- Bluetooth、swbt-python、Bumble、Switch 本体。
- 既存ボンド JSON の内容解釈、編集、ログ出力。
- 現行設計に存在しない旧 schema の推測実装。移行 registry と未知版拒否の境界だけを用意する。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/architecture.md`
- `spec/initial/configuration.md`
- `spec/initial/requirements.md`
- `spec/initial/testing.md`
- `spec/initial/naming.md`
- `AGENTS.md`
- `SKILLS.md`
- `spec/complete/unit_001/PROJECT_BOOTSTRAP.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| ドメイン値を構築する | finite な範囲内の値 | `ControllerFrame` と物理量が不変値として保持される | 外部型を import しない |
| 範囲外のドメイン値を拒否する | 非有限値、stick の `-1..1` 外 | 構築時に明示的な値エラーになる | 黙って clamp しない |
| Default profile を取得する | 組み込み preset 要求 | `Default` と全既定 binding を得る | 反転既定値は false |
| binding を検証する | 正規 source、target、amount、inverted | ボタン反転は許可し、stick target の inverted は拒否する | source の OS 固有記号は codec で保持する |
| 初期設定を生成する | settings.toml がない | schema v1、接続、色、入力、local action、Default profile の既定値を得る | OS パスは repository の責務 |
| 現行 TOML を往復する | 有効な AppSettings | encode/decode 後に同値になる | binding 配列を差分保存しない |
| 未知 schema を拒否する | 将来版または不明 schema | 元入力を既定値で上書きせず、unsupported result/error を返す | 安全な既定値への黙った保存を禁止 |
| 破損設定を復旧する | 構文または意味エラー | 元を日時付き backup へコピーし、Default settings を返す | backup 失敗時も元を上書きしない |
| 設定を原子的に保存する | 有効な AppSettings | 同一ディレクトリの一時ファイルを replace し、一時ファイルを残さない | UTF-8、LF、flush/fsync を試みる |
| OS パスを解決する | `PlatformDirs` | config、data、log の各ディレクトリを得る | `Project_Demi` の app name を固定する |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-done | domain の列挙型と値オブジェクトが不変で、finite/range 契約を守る | new / edge | unit | 8 tests green。例外型、docstring、型検査を green 後に整理 |
| todo | Binding、Profile、Default preset が全既定入力と反転属性を保持する | new | unit | Unit 003 の入力変換が使う設定境界 |
| todo | AppSettings の既定値と nested settings が schema v1 の制約を満たす | new / edge | unit | 色、timeout、感度、pitch limit、local action |
| todo | 現行 AppSettings が TOML encode/decode で同値往復する | new | unit | `tomli-w` は config 層だけで使う |
| todo | 未知 schema、未知項目、無効 enum/range を安全に拒否する | new / edge | unit | 未知の新版を既定値で保存しない |
| todo | PlatformDirs と bond slot のパス境界を検証する | new / edge | unit | パストラバーサル、OS 固定パスを禁止 |
| todo | repository が初回、正常、破損復旧、原子的保存を区別する | new / regression / edge | unit | backup と replace failure の fixture を使う |
| todo | package dependency、lock、build、typed import の gate が通る | characterization | package | `uv lock --check` と `uv build` を含める |

## 7. 設計メモ

- domain は `dataclass(frozen=True, slots=True)` と列挙型を使い、`platformdirs`、`tomli_w`、`pyglet` を import しない。
- codec は TOML の raw mapping と domain settings の変換を担当し、repository はファイル I/O、backup、atomic replace を担当する。
- 現行 schema は `demi.settings/v1`。migration registry は現行 schema を通過させ、未知 schema を `UnsupportedSchemaError` として扱う。旧版 fixture が定義されていないため、旧版の意味を推測して変換しない。
- 設定の未知項目は失敗扱いにし、将来項目を現行アプリが黙って実行時機能へ反映しない。
- binding の source/target は外部 library enum ではなく正規文字列として保存し、Unit 003 で入力 backend の値をこの境界へ正規化する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | `platformdirs`、`tomli-w` の runtime dependency |
| `uv.lock` | modify | 依存 lock |
| `src/demi/domain/controller.py` | new | ControllerFrame と物理量 |
| `src/demi/domain/mapping.py` | new | binding、profile、target/source |
| `src/demi/domain/settings.py` | new | AppSettings と nested settings |
| `src/demi/domain/errors.py` | new | domain/config error |
| `src/demi/config/paths.py` | new | platformdirs と bond path |
| `src/demi/config/validation.py` | new | raw/domain 制約 |
| `src/demi/config/codec.py` | new | TOML raw mapping と settings |
| `src/demi/config/migrations.py` | new | schema registry と未知版判定 |
| `src/demi/config/repository.py` | new | load/save、backup、atomic replace |
| `tests/unit/domain/test_controller.py` | new | domain value behavior |
| `tests/unit/domain/test_mapping.py` | new | binding と Default preset |
| `tests/unit/domain/test_settings.py` | new | AppSettings 制約 |
| `tests/unit/config/test_codec.py` | new | TOML 往復と schema |
| `tests/unit/config/test_paths.py` | new | path と bond slot |
| `tests/unit/config/test_repository.py` | new | 初回、復旧、原子的保存 |
| `tests/fixtures/settings/` | new | current/invalid/unknown schema fixture |
| `spec/complete/unit_002/DOMAIN_AND_SETTINGS.md` | new / modify | TDD 状態、検証、完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv sync --dev` | passed | unit_001 merge 後の baseline |
| `uv lock --check` | passed | unit_001 merge 後の baseline |
| `uv run ruff format --check .` | passed | unit_001 merge 後の baseline |
| `uv run ruff check .` | passed | unit_001 merge 後の baseline |
| `uv run ty check --no-progress` | passed | unit_001 merge 後の baseline |
| `uv run pytest tests/unit` | passed | 5 passed、unit_001 merge 後 |
| `uv build` | passed | unit_001 merge 後の baseline artifact |
| `uv run pytest tests/integration` | not applicable | `tests/integration` tree は未作成 |
| `uv run pytest tests/unit/domain/test_controller.py` | passed | 8 passed |
| `uv run ruff format --check src/demi/domain tests/unit/domain/test_controller.py` | passed | 4 files already formatted |
| `uv run ruff check src/demi/domain tests/unit/domain/test_controller.py` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |

## 10. 先送り事項

- schema v1 より前の仕様が確定していないため、旧版からの実データ移行は後続の仕様で fixture とともに追加する。
- GUI からの設定編集、保存遅延、復旧メッセージ表示は Unit 007 で扱う。
- `ControllerColors` など swbt 型への変換は Unit 006 で扱う。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を作成した
- [ ] 検証結果または未実行理由を実装後に更新した
- [ ] package / release / public API に触れる場合の gate を記録した
- [ ] 完了時に `spec/complete/unit_002` へ移動した
