# Hardware test log

No Project_Demi hardware test had been executed at the initial-design stage on 2026-07-10.

Every future entry must record:

- Date, time, and timezone
- Project_Demi commit
- Python version
- swbt-python version
- Bumble version
- PySide6版、Qt版
- Operating system and version
- USB Bluetooth adapter model and VID/PID
- Driver
- Adapter identifier
- Target device and firmware
- Pairing or reconnect flow
- Exact test cases
- Result and observed limitations

Do not convert an upstream swbt-python observation into a Project_Demi hardware result. Record only tests executed through Project_Demi.

## Unit 008 scope record — 2026-07-13 JST

This record intentionally does not claim a hardware acceptance result. The user-requested delivery scope excludes Bluetooth dongle and Switch hardware verification.

| item | value |
|---|---|
| Project_Demi implementation reference | `49c26b6` |
| execution status | not run |
| reason | current delivery scope excludes Bluetooth dongle and Switch hardware verification |
| hardware command | not run |
| Python / swbt-python / Bumble / PySide6 / Qt | not collected for a hardware run |
| operating system | not collected for a hardware run |
| USB adapter, VID/PID, driver, adapter identifier | not run — no adapter was used |
| target device and firmware | not run — no Switch device was used |
| pairing or reconnect flow | not run — hardware scope excluded |
| exact test cases | new pairing, saved-bond reconnect, input matrix, gyro, adapter removal, target disconnect, shutdown safety: not run |
| result | none; runtime stability was verified with fake adapters only |
| observed limitations | Windows 11 / Bluetooth / Switch acceptance remains unverified |

The manual entrypoint is `uv run pytest tests/hardware -m "hardware and bumble" -q`. It performs only an explicit preflight and is not an acceptance pass. A future operator must record every field above and the exact scenarios executed through Project_Demi.

## Unit 024 saved-bond reconnect preflight — 2026-07-16 12:35–12:38 JST

This record is not a gyro acceptance result. Project_Demi reached the saved-bond reconnect boundary, but the target did not reconnect before the configured 10-second timeout.

| item | value |
|---|---|
| Project_Demi implementation reference | `12a8007` |
| execution status | failed before hardware acceptance |
| date, time, timezone | 2026-07-16 12:35:55–12:38:39 JST |
| Python / swbt-python / Bumble | Python 3.12.10 / swbt-python 0.3.0 / Bumble 0.0.230 |
| PySide6 / Qt | PySide6 6.11.1 / Qt 6.11.1 |
| operating system | Windows 11 10.0.26200 |
| USB adapter | CSR8510 A10, Cambridge Silicon Radio, Ltd, VID `0A12`, PID `0001` |
| driver | libwdi 6.1.7600.16385, dated 2012-06-02, unsigned |
| adapter identifier | `usb:0`; GUI displayed `CSR8510 A10` and one detected USB adapter |
| target device and firmware | not collected; saved `pro_controller` configuration and bond file do not prove the connected target or firmware |
| pairing or reconnect flow | Launched `.venv\\Scripts\\demi.exe`, opened connection settings, retained bond slot `default`, selected `保存して接続`, and waited beyond the 10-second timeout |
| exact test cases | application startup: passed; Raw Input capability: passed; USB adapter discovery: passed; saved-bond reconnect: failed; input capture and low/medium/high horizontal/vertical gyro movement: not run |
| result | GUI moved from `接続中` to `準備完了` and displayed `保存済み接続に失敗しました`; log recorded `Controller error: RECONNECT_FAILED` at 12:38:39 JST |
| observed limitations | target power, reconnect screen, pairing state, target model, and firmware were not verified; no conclusion can be drawn about game-camera smoothness |

## Unit 039 Direct送信実機試験 — 2026-07-20 JST

この記録はProject_Demiを通した実機試験と、その後の診断ログ採取の結果である。#44 の受入条件である実機結果の記録は完了した。ジャイロ操作感の未解決事項は #45 で追跡し、この記録を受入成功として扱わない。

| item | value |
|---|---|
| Project_Demi implementation reference | 初回実機試験: `3958cb5`; 診断ログ採取: `ac37dfc` 以降 |
| execution status | #44 の実機結果を記録済み。ジャイロ操作感は未解決で #45 に分離 |
| date, time, timezone | 2026-07-20 JST; 実行時刻は記録されていない |
| Python / swbt-python / Bumble | Python 3.12.10 / swbt-python 0.4.0 / Bumble 0.0.230 |
| PySide6 / Qt | PySide6 6.11.1 / Qt 6.11.1 |
| operating system | Microsoft Windows 11 Pro 10.0.26200 |
| USB adapter | CSR8510 A10, VID `0A12`, PID `0001` |
| driver | libwdi 6.1.7600.16385, dated 2012-06-02, unsigned; Unit 024記録から再利用し、この試験時には再取得していない |
| adapter identifier | `usb:0`; aliases `usb:0A12:0001` |
| target device and firmware | Nintendo Switch 2, firmware 22.5.0 |
| pairing or reconnect flow | 明示的なpairing、接続、切断を実施。saved-bond reconnectはこの記録の対象外 |
| exact test cases | pairing、接続、切断、`Start mouse`なしのF→A、`Start mouse`ありのF→A、マウスジャイロ操作、Direct送信DEBUGログの採取 |
| result | pairing、接続、切断: passed。F→A: `Start mouse`ありでSwitchが認識し、診断ログではポインター未捕捉時を含むAの`send()`完了を記録した。ジャイロ: カクつきを観測 |
| observed limitations | Direct送信のDEBUGログは、F→Aの送信完了とframe集約を記録するが、送信時間とIMU slotごとの時系列を記録しない。ジャイロのカクつきとframe集約の因果関係は未確認であり、#45 で追跡する |

`ac37dfc`以降のDEBUGログで、送信済みボタン状態とframe集約区間を採取した。#45 では同じ操作列に送信時間とIMU時系列の記録を加え、実機操作感と対応付ける。

## Unit 060 Python 3.13 / swbt-python 0.6実機確認 — 2026-07-27 JST

この記録は、#45で追跡した125 Hz回転時の周期的なカクつきについて、
Python 3.13とswbt-python 0.6へ更新したProject_Demiを通して再確認した結果である。
接続・切断・保存済み再接続を含む包括的な受入試験ではない。

| item | value |
|---|---|
| Project_Demi implementation reference | `57104d8` |
| execution status | 125 Hz回転の目視確認: passed |
| date, time, timezone | 2026-07-27 JST。実行時刻は記録されていない |
| Python / swbt-python / Bumble | Python 3.13.5 / swbt-python 0.6.0 / Bumble 0.0.233 |
| PySide6 / Qt | PySide6 6.11.1 / Qt 6.11.1 |
| operating system | Windows 11 10.0.26200 |
| USB adapter, VID/PID, driver, adapter identifier | この確認では再採取していない |
| target device and firmware | この確認では再採取していない |
| pairing or reconnect flow | この確認では手順を記録していない |
| exact test cases | 隔離worktreeから`uv run demi`を起動し、125 Hzで回転を実機目視 |
| result | 回転は滑らかで、#45で観測した周期的なカクつきは見えなかった |
| observed limitations | 目視確認であり、厳密な125 Hz送信保証や遅延計測ではない。Python 3.14、接続経路、機器情報はこの確認の対象外 |

## Issue #45 Python 3.12 timer診断記録 — 2026-07-26 JST

この記録は、Unit 060の更新前にPython 3.12.10 / swbt-python 0.5.1で行った
8 ms、16 ms、8 msの比較を、上流調査で確定したtimer原因に基づいて要約したものである。
実験用ACL/HCI probeはswbt-pythonのprivate実装を観測した一時コードであり、製品には残さない。

| item | value |
|---|---|
| Project_Demi implementation reference | `e20a04f`を基点とする未commitの`experiment/issue-45-acl-probe` |
| execution status | 8 ms、16 ms、8 msの比較とHCI sink直前の時系列をobserved |
| date, time, timezone | 2026-07-26 23:06:34–23:26:39 JST |
| Python / swbt-python / Bumble | Python 3.12.10 / swbt-python 0.5.1 / Bumbleは未採取 |
| PySide6 / Qt | PySide6 6.11.1 / Qt 6.11.1 |
| operating system | Windows 11。build番号はこの実行では未採取 |
| USB adapter, VID/PID, driver, adapter identifier | この実行では再採取していない。Unit 039の機器情報を参照 |
| target device and firmware | Switch画面を観測。機種とfirmwareはこの実行では再採取していない |
| pairing or reconnect flow | 保存済み接続を使用 |
| exact test cases | `J`による一定yawを、8 ms、プロセス限定の16 ms、環境変数を外した8 msの順で実行 |
| result | 8 msでは周期的なカクつきあり、16 msではなし、8 msへ戻すと再現 |
| observed limitations | 各条件1回の目視比較。厳密な送信周波数、遅延、画面反映時刻は測定していない |

### 観測値

| evaluation period | HCI reports | gap under 2 ms | gap 12–20 ms | 12–20 ms後に2 ms未満 | 12–20 ms gap間隔 | Switch画面 |
|---|---:|---:|---:|---:|---:|---|
| 8 ms | 2,060 | 48.86% | 51.14% | 94.68% | 15.625 ms | 周期的なカクつきあり |
| 16 ms | 394 | 1.02% | 96.18% | 0.53% | 16.536 ms | カクつきなし |
| 8 msへ復帰 | 720 | 48.96% | 51.04% | 94.01% | 15.626 ms | 周期的なカクつきあり |

8 ms実行ではProject_Demiの送信開始間隔は約8 msで、yaw区間のframe併合と
`send()`受理待ちは観測されなかった。一方、Bumble hostがHCI sinkへ渡す直前では、
約15.625 msの空白と2 ms未満の近接送出にほぼ二分された。16 ms実行では近接送出が
1.02%へ減り、画面のカクつきも見えなくなった。

実験時点ではHCI credit処理を原因候補としたが、上流の追加調査によりこの解釈は棄却した。
WindowsのPython 3.12では`time.monotonic()`が15.625 ms分解能の`GetTickCount64()`を使い、
Python 3.13.5では100 ns分解能の`QueryPerformanceCounter()`を使う。同じ8 ms入力を
Python 3.13.5で実行すると滑らかになり、HCI queueの待機最大値も0だった。
したがって、probeが捉えた15.625 msの形はtimer量子化が下流へ現れた結果であり、
HCI credit枯渇の証拠ではない。

根拠は[swbt-python Issue #152](https://github.com/niart120/swbt-python/issues/152#issuecomment-5084478982)
と、Python 3.13 / swbt-python 0.6へ更新した[PR #62](https://github.com/niart120/demi-controller/pull/62)
を参照する。
