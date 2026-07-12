# Development journal

## 2026-07-10: Initial design

- Project name fixed as `Project_Demi`.
- Python distribution name fixed as `project-demi`.
- Root package fixed as `demi`.
- Selected pyglet 2.1 as the windowing, drawing, and focused input layer.
- Selected swbt-python 0.2 as the Bluetooth HID boundary.
- Selected a pyglet main thread plus a dedicated asyncio controller worker.
- Defined `Default` as the built-in input profile.
- Generalized active-low button mappings as the per-binding `inverted` property; no target-specific inversion path is used.
- Rejected the old serial/TCP 21-byte transport from the new architecture.
- Added fail-safe neutralization for focus loss, capture release, disconnect, shutdown, and a 250 ms UI-frame watchdog.
- The specified public template URL was not retrievable while writing the design. The public swbt-python repository structure was used as the concrete agentic-project reference.

## 2026-07-10: YawPitchModel

- Adopted `YawPitchModel` for mouse-to-gyro conversion.
- Horizontal input is world-up yaw; vertical input is pitch with a default ±75-degree limit.
- Removed virtual-radius and vertical-position settings from the normative design.
- Defined horizontal and vertical sensitivity as independent dimensionless multipliers with `1.0` as the standard value.
- Standardized runtime angle and angular-velocity calculations on radians and radians per second.
- Moved the model comparison and selection rationale to `spec/initial/appendix/aim-model.md`.


## 2026-07-11: Delegate gyro encoding to swbt-python

- Replaced the domain raw `GyroSample` with `GyroRate` in radians per second.
- Removed the Project_Demi `GyroEncoder` and all local raw-scale constants.
- Made swbt-python issue #69 and `IMUFrame.gyro_rate()` a prerequisite for gyro integration.
- Kept controller calibration, virtual SPI data, and rad/s-to-raw conversion in one library-side contract.

## 2026-07-11: Add pose-consistent static acceleration

- Audited Nintendo Switch IMU axis directions against Linux `hid-nintendo`, dekuNukem IMU/SPI notes, and SDL's Switch driver.
- Fixed the canonical domain axes to +X toward triggers, +Y left, and +Z out of the button/stick face.
- Defined horizontal static rest as `AccelG(0, 0, +1)` and pitch-dependent rest as `(-sin(pitch), 0, cos(pitch))`.
- Kept Right Joy-Con Y/Z normalization out of `YawPitchModel`; future device-specific correction belongs at the profile-aware adapter boundary.
- Added swbt-python issue #70 and `with_accel_g()` as prerequisites alongside issue #69.
- Replaced steady-state use of zero-G `neutral()` with an explicitly applied physical rest `InputState`.

Pinned sources:

- https://github.com/torvalds/linux/blob/dd3210c47e8d3ac6b4e9141fc68acc03b38c0ba3/drivers/hid/hid-nintendo.c
- https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering/blob/ac8093c84194b3232acb675ac1accce9bcb456a3/imu_sensor_notes.md
- https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering/blob/ac8093c84194b3232acb675ac1accce9bcb456a3/spi_flash_notes.md
- https://github.com/libsdl-org/SDL/blob/9149eca2077940bdfa29e743a7cf3aafbf10e3dc/src/joystick/hidapi/SDL_hidapi_switch.c
