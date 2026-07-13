# Hardware test log

No Project_Demi hardware test had been executed at the initial-design stage on 2026-07-10.

Every future entry must record:

- Date, time, and timezone
- Project_Demi commit
- Python version
- swbt-python version
- Bumble version
- pyglet version
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
| Python / swbt-python / Bumble / pyglet | not collected for a hardware run |
| operating system | not collected for a hardware run |
| USB adapter, VID/PID, driver, adapter identifier | not run — no adapter was used |
| target device and firmware | not run — no Switch device was used |
| pairing or reconnect flow | not run — hardware scope excluded |
| exact test cases | new pairing, saved-bond reconnect, input matrix, gyro, adapter removal, target disconnect, shutdown safety: not run |
| result | none; runtime stability was verified with fake adapters only |
| observed limitations | Windows 11 / Bluetooth / Switch acceptance remains unverified |

The manual entrypoint is `uv run pytest tests/hardware -m "hardware and bumble" -q`. It performs only an explicit preflight and is not an acceptance pass. A future operator must record every field above and the exact scenarios executed through Project_Demi.
