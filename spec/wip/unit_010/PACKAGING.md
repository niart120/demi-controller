# パッケージング 仕様書

## 1. 概要

### 1.1 目的

PyInstaller を standalone builder として固定し、canonical CLI を Windows、macOS、Linux の one-file launcher へ変換する。artifact に版情報、プロジェクトライセンス、runtime dependency の license 一覧を添え、各 OS の clean runner で `--version` が起動する workflow を用意する。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| roadmap | PyInstaller / Nuitka の選択、OS 別配布物、assets、license、起動ログ、版情報 | `spec/initial/roadmap.md` |
| requirements | Windows / macOS / Linux の別 build、local-only、pyglet 中心 | `spec/initial/requirements.md` |
| risks | Bumble / libusb / pyglet resource の収集漏れ | `spec/initial/risks.md` |
| publishing | local preflight、production publish の停止条件 | `spec/publishing.md` |
| current package | canonical CLI、version metadata、wheel / sdist | `src/demi/cli.py`, `pyproject.toml` |
| user scope | Bluetooth / Switch 本体の実機検証完了は対象外 | user request |

### 1.3 builder comparison

| candidate | observation | decision |
|---|---|---|
| PyInstaller | Python package を one-file executable へ変換し、Windows / macOS / Linux の runner で同じ command を使える | adopt |
| Nuitka | native compiler toolchain と OS ごとの compiler setup が必要で、現行 package に対する追加検証範囲が大きい | not selected |

### 1.4 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| maintainer | OS runner、Python 3.12、locked dev dependencies | PyInstaller artifact と VERSION / LICENSES / BUILD_INFO が生成される | 交差 build をしない |
| user | standalone artifact、`--version` | package metadata と同じ `0.1.0` を表示して終了コード 0 になる | Bluetooth / display は version smoke で要求しない |
| release workflow | Windows / macOS / Linux matrix | OS ごとの artifact を保存できる | hardware test は含めない |
| maintainer | runtime dependency inventory | direct dependency と license file の一覧を artifact 内へ置く | license 内容を推測で補わない |

## 2. 対象範囲

- PyInstaller を dev dependency と workflow builder に固定する。
- `packaging/launcher.py` から canonical `demi.cli:main` を起動する。
- `packaging/build.py` で one-file artifact、VERSION.txt、BUILD_INFO.txt、LICENSES/ を生成する。
- runtime package の license file を installed distribution metadata から収集する。
- `packaging/smoke.py` で OS に応じた executable の `--version` を実行する。
- `workflow_dispatch` と `v*` tag を入口に Windows / macOS / Linux artifact workflow を追加する。
- artifact に assets が存在する場合だけ収集し、現行 0.1.0 の asset inventory は空であることを記録する。

## 3. 対象外

- Bluetooth dongle、Bumble、Switch 本体を使う接続・入力・pairing。
- standalone artifact の実ウィンドウ、OpenGL、DPI、exclusive mouse、font rendering。
- OS 別 clean display environment での GUI acceptance。
- PyPI / TestPyPI への production publish（明示承認付きの release workflow で別途扱う）。
- GUI application assembly や未実装の settings / connection button wiring を packaging の成功条件にすること。
- Nuitka の実 build と benchmark。

## 4. 関連 docs

- `spec/initial/roadmap.md`
- `spec/initial/requirements.md`
- `spec/initial/risks.md`
- `spec/initial/architecture.md`
- `spec/publishing.md`
- `spec/complete/unit_009/OS_PORTABILITY.md`
- `AGENTS.md`
- `SKILLS.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| builder を選ぶ | candidate comparison | PyInstaller が採用され、Nuitka は未採用理由を記録する | toolchain の増加を避ける |
| launcher を build する | source root、PyInstaller、OS runner | `dist/standalone/demi` または `demi.exe` が生成される | one-file、OS ごとに native build |
| version を確認する | standalone binary、`--version` | package metadata の `0.1.0` と一致し、終了コード 0 になる | hardware / display 不要 |
| build metadata を保存する | standalone output | VERSION、BUILD_INFO、license inventory が artifact に含まれる | absolute local path を含めない |
| license を収集する | installed runtime distributions | project MIT と runtime dependency license file を一覧化する | package metadata が持つ file だけを使う |
| release workflow を起動する | manual dispatch または `v*` tag | 3 OS の artifact を upload する | publish は実行しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| green | PyInstaller を採用し、launcher が canonical CLI へ委譲する | new | package | packaging contract test と launcher を確認した |
| green | build script が one-file artifact、version、build info、license inventory を生成する | new | package | Windows artifact と installed metadata の license file を確認した |
| green | standalone binary の `--version` smoke が Windows runner で pass する | new | package | `demi.exe` が `0.1.0` を返した |
| green | OS 別 package workflow が Windows / macOS / Linux artifact を定義する | new | package | workflow 構造を repository test で固定した |
| green | unit / integration / static / lock / build / package gate が通る | characterization | package | sdist / wheel、twine、standalone smoke を含めた |

## 7. 設計メモ

- `packaging/build.py` は project root から実行し、PyInstaller の work path と standalone output path を固定する。既存の `dist` wheel / sdist と混ぜない。
- launcher は `demi.cli:main` だけを起動し、`--version` smoke が display や hardware へ依存しないようにする。swbt / pyglet の収集指定は artifact の dependency completeness のために行う。
- license inventory は `importlib.metadata` の installed files から direct runtime dependency とその license file をコピーする。取得できない license file は成功扱いにしない。
- BUILD_INFO は version、OS、Python、PyInstaller の版だけを含め、ユーザー path、bond path、adapter metadata は含めない。
- current repository に runtime asset directory はない。asset inventory は空の結果を明示し、将来追加時に build script へ収集対象を追加する。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml` | modify | PyInstaller dev dependency |
| `uv.lock` | modify | PyInstaller dependency lock |
| `packaging/launcher.py` | new | canonical CLI launcher |
| `packaging/build.py` | new | PyInstaller build、metadata、license inventory |
| `packaging/smoke.py` | new | OS 別 executable version smoke |
| `packaging/LICENSES.md` | new | direct dependency license inventory policy |
| `.github/workflows/package.yml` | new | OS 別 standalone artifact workflow |
| `tests/unit/test_packaging.py` | new | packaging manifest / workflow contract |
| `README.md` | modify | standalone build と smoke の入口 |
| `spec/publishing.md` | modify | release preflight に standalone build を追加 |
| `spec/complete/unit_010/PACKAGING.md` | new | 完了記録 |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run pytest tests/unit/test_packaging.py -q` | passed | 2 passed。launcher、build script、OS artifact workflow の contract を確認 |
| `uv sync --dev` | passed | 74 packages resolved、71 packages checked。PyInstaller 6.21.0 を含む |
| `uv lock --check` | passed | lockfile は最新 |
| `uv run ruff format --check .` | passed | 79 files already formatted |
| `uv run ruff check .` | passed | All checks passed |
| `uv run ty check --no-progress` | passed | All checks passed |
| `uv run pytest tests/unit` | passed | 122 passed。Windows local runner |
| `uv run pytest tests/integration` | passed | 11 passed。Windows local runner |
| `uv run pytest -m "not hardware and not bumble"` | passed | 133 passed、1 deselected |
| `uv run python packaging/build.py` | passed | Windows 11、PyInstaller 6.21.0、`dist/standalone/demi.exe` 30.6 MB、libusb DLL、VERSION / BUILD_INFO / LICENSES を生成 |
| `uv run python packaging/smoke.py` | passed | `demi.exe --version` が `0.1.0`、終了コード 0 |
| standalone metadata smoke | passed | project / runtime license inventory と build info を確認 |
| `uv build` | passed | `demi_controller-0.1.0.tar.gz` と `demi_controller-0.1.0-py3-none-any.whl` を生成 |
| `uv run twine check --strict dist/*.whl dist/*.tar.gz` | passed | wheel / sdist metadata valid |
| wheel / sdist smoke | passed | wheel package metadata、sdist packaging sources を確認 |
| `git diff --check` | passed | whitespace error なし |
| GitHub Actions OS CI | passed | run `29218727033` の Ubuntu / macOS / Windows × Python 3.12 / 3.13、6 jobs がすべて pass |
| GitHub Actions package matrix | not run | workflow_dispatch は workflow が default branch に入った後に実行する |

## 10. 先送り事項

- standalone artifact の実ウィンドウ、display、exclusive mouse、Bluetooth 接続は未検証。
- Windows build では PyInstaller が optional な pyglet X11、Bumble pandora、wintab32 module を収集できない warning を出した。Windows の version smoke は通ったが、各 OS の実機能に必要な resource 完備は OS 別 artifact で確認する。
- PyPI / TestPyPI publish は明示承認と trusted publishing 設定確認が必要。
- assets は現行 inventory が空。新規 assets 追加時に license と収集テストを追加する。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test List を更新した
- [x] 検証結果または未実行理由を実装後に更新した
- [x] standalone artifact の version / license / build info を確認した
- [x] package / release / public API に触れる場合の gate を記録した
