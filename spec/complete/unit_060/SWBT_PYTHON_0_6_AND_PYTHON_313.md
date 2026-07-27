# swbt-python 0.6 / Python 3.13移行 仕様書

## 1. 概要

### 1.1 目的

swbt-python 0.6.0が要求するPython 3.13以上へProject_Demiの実行環境を引き上げ、
Windowsの高分解能monotonic clockを使う。Direct送信契約は変更せず、依存、CI、
静的解析、利用者向け案内、保存済み接続プロファイルの互換性説明を整合させる。

### 1.2 起点 / source

| source | 内容 | path |
|---|---|---|
| user request | swbt-python v0.6.0とPython 3.13下限へ追従する | conversation, 2026-07-27 |
| upstream investigation | Python 3.12のWindows monotonic clockは15.625 ms、Python 3.13.5は100 ns分解能で、同じ8 ms入力が滑らかになった | `https://github.com/niart120/swbt-python/issues/152#issuecomment-5084478982` |
| upstream release | 公開APIと送信処理を変えず、Python 3.13以上を必須にした | `https://github.com/niart120/swbt-python/releases/tag/v0.6.0` |
| upstream migration | 0.5.3以降のschema v2は0.5.1のschema v1 profileを読まず、再ペアリングを要求する | swbt-python `docs/release-notes.md` |

### 1.3 use case

| actor / boundary | 入力または状態 | 期待する観測結果 | 制約 |
|---|---|---|---|
| source / wheel利用者 | Project_Demiをinstallする | Python 3.13以上とswbt-python 0.6系が解決する | Python 3.12ではinstall不可 |
| CI保守者 | 通常gateを実行する | Python 3.13 / 3.14でunit、integration、buildを検証する | Python 3.12を行列へ残さない |
| 既存利用者 | swbt-python 0.5.1で作成した保存済みprofileを持つ | 互換性がないことと削除後の再ペアリング手順を確認できる | 自動変換・上書きを行わない |
| 実機操作者 | Python 3.13で8 ms Direct入力を確認する | #45で観測した周期的カクつきの再確認条件が揃う | 厳密な125 Hzは保証しない |

## 2. 対象範囲

- Project_Demiの最低Pythonを3.13へ変更する。
- CIと静的解析の対象をPython 3.13 / 3.14へ変更する。
- swbt-pythonを`>=0.6.0,<0.7.0`へ更新し、lockを再生成する。
- 初期仕様とREADMEへtimer調査結果、対応範囲、profile再ペアリング要否を反映する。
- swbt-python 0.6.0の既存Direct公開契約を自動試験で確認する。

## 3. 対象外

- `asyncio`、Qt、swbt-python、Bumbleの時計をProject_Demiから差し替えること。
- Direct送信周期、mailbox、IMU frame構成、入力評価周期の変更。
- schema v1 profileの読込、自動移行、自動削除。
- Python 3.14でのSwitch実機確認。
- OS負荷を含む厳密な8 ms / 125 Hz保証。

## 4. 関連 docs

- `spec/initial/README.md`
- `spec/initial/roadmap.md`
- `spec/initial/swbt-integration.md`
- `spec/initial/testing.md`
- `spec/initial/risks.md`
- `spec/complete/unit_040/SWBT_PYTHON_0_5_MIGRATION.md`

## 5. 振る舞い仕様

| 振る舞い | 入力・状態 | 期待結果 | 備考 |
|---|---|---|---|
| Python下限 | package metadataを読む | `requires-python >=3.13`で、3.13 / 3.14を対応版として宣言する | 3.12 classifierを除く |
| 静的解析 | ruff / ty設定を読む | 最低版と同じPython 3.13を解析対象にする | 3.13構文の利用を許可する |
| CI | workflowを読む | 3 OS × Python 3.13 / 3.14で既存gateを実行する | hardwareは含めない |
| swbt依存 | lock / installed metadataを読む | swbt-python 0.6系とBumble 0.0.233を解決し、必要なDirect公開APIを利用できる | 0.7以降を許可しない |
| profile互換性 | 0.5.1の保存済みprofileがある | incompatible errorを既存の保存情報エラーとして扱い、利用者が明示削除して再ペアリングする | 自動移行しない |
| timer境界 | Windows / Python 3.13で起動する | Python標準の高分解能monotonic clockを利用する | 独自時計を注入しない |

## 6. TDD Test List

| status | item | type | layer | notes |
|---|---|---|---|---|
| refactor-skipped | package metadata、ruff、ty、CIがPython 3.13下限と3.13 / 3.14対応を一貫して宣言する | change | package | 旧3.12設定と`.python-version`でredを確認し、設定値を揃えてgreen |
| refactor-skipped | swbt-python 0.6系が解決され、Project_Demiが使うDirect公開契約を維持する | regression | package / unit | 旧0.5系の宣言とinstall結果でredを確認し、0.6.0へ更新してgreen |
| refactor-skipped | READMEと初期仕様がPython下限、timer調査、profile v1非互換、未保証範囲を正確に説明する | regression | docs | 文書の事実整合、配置、仮テキストをreview |
| refactor-skipped | Python 3.13環境で標準gateと配布物検証が成功する | regression | unit / integration / package | Python 3.13で全gate成功。3.14でもunit、integration、配布物検証成功 |

## 7. 設計メモ

swbt-python 0.6.0は送信実装で時計を差し替えていない。Project_Demiも独自の
`QueryPerformanceCounter` wrapperやWindows timer APIを追加せず、Python 3.13の標準
`time.monotonic()`と`asyncio`を使う。

0.5.1から0.6.0への更新では、0.5.3のprofile schema v2も取り込む。Project_Demiはprofile
本文を所有しないため変換しない。既存の削除操作とincompatible profile errorを利用し、
削除後に新規ペアリングする。

## 8. 対象ファイル

| path | change | 内容 |
|---|---|---|
| `pyproject.toml`, `uv.lock` | modify | Python下限、swbt依存、静的解析対象、lock |
| `.github/workflows/ci.yml` | modify | Python 3.13 / 3.14行列 |
| `tests/unit/` | new / modify | package契約とswbt 0.6公開契約 |
| `README.md`, `spec/initial/*.md` | modify | 利用条件、移行、外部事実、リスク |

## 9. 検証

| command | result | notes |
|---|---|---|
| `uv run --python 3.13 pytest tests/unit/test_runtime_floor.py -q` | pass | Python下限変更前と`.python-version`変更前にそれぞれredを確認し、変更後2件pass |
| `uv run --python 3.13 pytest tests/unit/controller/test_swbt_dependency.py -q` | pass | 依存更新前に宣言・install版のredを確認し、変更後26件pass |
| `uv sync --dev` | pass | Python 3.13.5、swbt-python 0.6.0を同期 |
| `uv lock --check` | pass | lockとmetadataが一致 |
| `uv run ruff format --check .` | pass | 155 files already formatted |
| `uv run ruff check .` | pass | lint errorなし |
| `uv run ty check --no-progress` | pass | type errorなし |
| `uv run pytest tests/unit` | pass | Python 3.13.5、361件pass |
| `uv run pytest tests/integration` | pass | Python 3.13.5、134件pass |
| `uv build` | pass | sdist / wheel作成成功 |
| `uv run python packaging/verify_distribution.py` | pass | 配布物検証成功 |
| `uv run --python 3.14 pytest tests/unit -q` | pass | Python 3.14.6、360件pass |
| `uv run --python 3.14 pytest -p no:cacheprovider --basetemp tmp/pytest-integration-314 tests/integration -q` | pass | Python 3.14.6、134件pass |
| `uv run --python 3.14 python packaging/verify_distribution.py` | pass | Python 3.14.6で配布物検証成功 |
| `uv run --python 3.13 python -c "import time,sys; print(sys.version.split()[0], time.get_clock_info('monotonic'))"` | pass | Python 3.13.5、QueryPerformanceCounter、resolution `1e-07` |
| `uv run demi`から125 Hz回転を実機観測 | pass | Python 3.13.5 / swbt-python 0.6.0で周期的なカクつきは見えず、回転が滑らかになった |
| `git diff --check` | pass | whitespace errorなし |

## 10. 先送り事項

- Python 3.13 / swbt-python 0.6.0で125 Hz回転が滑らかになったことを実機確認した。保存済み再接続を含む接続経路の詳細は、この確認では採取していない。
- Python 3.14のSwitch実機確認は上流でも未実行であり、本unitでは行わない。

## 11. チェックリスト

- [x] 対象範囲と対象外を確認した
- [x] TDD Test Listを更新した
- [x] 検証結果または未実行理由を記録した
- [x] package / release / public APIに触れる場合のgateを記録した
