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
