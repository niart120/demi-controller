"""Immutable application settings and their domain invariants."""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from .errors import DomainValueError
from .mapping import InputProfile, default_profile

SCHEMA = "demi.settings/v1"
_COLOR_PATTERN = re.compile(r"#[0-9A-Fa-f]{6}")


class ControllerType(StrEnum):
    """Controller kinds supported by the current release."""

    PRO_CONTROLLER = "pro_controller"


class DiagnosticLevel(StrEnum):
    """Supported logging thresholds for user diagnostics."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class UiLanguage(StrEnum):
    """Languages available for the desktop user interface."""

    ENGLISH = "en"
    JAPANESE = "ja"


def _require_integer_range(value: int, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise DomainValueError


def _require_float_range(value: float, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DomainValueError
    if not minimum <= value <= maximum:
        raise DomainValueError


@dataclass(frozen=True, slots=True)
class WindowSettings:
    """Window dimensions and initial maximized state."""

    width: int = 960
    height: int = 640
    maximized: bool = False

    def __post_init__(self) -> None:
        """Validate the supported window dimensions."""
        _require_integer_range(self.width, 800, 7680)
        _require_integer_range(self.height, 520, 4320)
        if not isinstance(self.maximized, bool):
            raise DomainValueError


@dataclass(frozen=True, slots=True)
class ConnectionSettings:
    """Application-wide connection selection and startup settings."""

    adapter_id: str = ""
    controller: ControllerType = ControllerType.PRO_CONTROLLER
    reconnect_on_start: bool = False
    diagnostic_level: DiagnosticLevel = DiagnosticLevel.INFO

    def __post_init__(self) -> None:
        """Validate application-wide connection values."""
        if not isinstance(self.adapter_id, str) or len(self.adapter_id) > 256:
            raise DomainValueError
        if not isinstance(self.controller, ControllerType):
            raise DomainValueError
        if not isinstance(self.reconnect_on_start, bool):
            raise DomainValueError
        if not isinstance(self.diagnostic_level, DiagnosticLevel):
            raise DomainValueError


@dataclass(frozen=True, slots=True)
class ControllerColorSettings:
    """Four ``#RRGGBB`` colors used by the controller view and adapter."""

    body: str = "#323232"
    buttons: str = "#0F0F0F"
    left_grip: str = "#323232"
    right_grip: str = "#323232"

    def __post_init__(self) -> None:
        """Validate and normalize all color values."""
        for field_name in ("body", "buttons", "left_grip", "right_grip"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or _COLOR_PATTERN.fullmatch(value) is None:
                raise DomainValueError
            object.__setattr__(self, field_name, value.upper())


@dataclass(frozen=True, slots=True)
class MouseSettings:
    """Mouse-to-IMU settings applied by the input publisher."""

    gyro_enabled: bool = True
    horizontal_sensitivity: float = 1.0
    vertical_sensitivity: float = 1.0
    invert_y: bool = False
    pitch_limit_degrees: float = 75.0
    invert_x: bool = False

    def __post_init__(self) -> None:
        """Validate mouse-to-IMU fields."""
        if not isinstance(self.gyro_enabled, bool):
            raise DomainValueError
        _require_float_range(self.horizontal_sensitivity, 0.1, 10.0)
        _require_float_range(self.vertical_sensitivity, 0.1, 10.0)
        if not isinstance(self.invert_x, bool) or not isinstance(self.invert_y, bool):
            raise DomainValueError
        _require_float_range(self.pitch_limit_degrees, 1.0, 89.0)


@dataclass(frozen=True, slots=True)
class InputSettings:
    """Input evaluation and stick policy settings."""

    evaluation_interval_ms: int = 8
    circular_stick_limit: bool = False
    mouse: MouseSettings = field(default_factory=MouseSettings)

    def __post_init__(self) -> None:
        """Validate evaluation interval and nested mouse settings."""
        _require_integer_range(self.evaluation_interval_ms, 4, 32)
        if not isinstance(self.circular_stick_limit, bool):
            raise DomainValueError
        if not isinstance(self.mouse, MouseSettings):
            raise DomainValueError


@dataclass(frozen=True, slots=True)
class LocalActions:
    """Keyboard shortcuts owned by the application rather than bindings."""

    toggle_capture: tuple[str, ...] = ("CTRL+C",)
    quit: tuple[str, ...] = ("CTRL+Q",)
    connection: tuple[str, ...] = ("CTRL+RETURN", "CTRL+ENTER")

    def __post_init__(self) -> None:
        """Validate local action names without importing an input backend."""
        for action in (
            self.toggle_capture,
            self.quit,
            self.connection,
        ):
            if not isinstance(action, tuple) or not all(
                isinstance(value, str) and value for value in action
            ):
                raise DomainValueError


@dataclass(frozen=True, slots=True)
class UiSettings:
    """Desktop user interface preferences."""

    language: UiLanguage = UiLanguage.ENGLISH

    def __post_init__(self) -> None:
        """Validate the selected user interface language."""
        if not isinstance(self.language, UiLanguage):
            raise DomainValueError


@dataclass(frozen=True, slots=True)
class AppSettings:
    """Complete validated application settings snapshot."""

    schema: str = SCHEMA
    active_profile: str = "default"
    ui: UiSettings = field(default_factory=UiSettings)
    window: WindowSettings = field(default_factory=WindowSettings)
    connection: ConnectionSettings = field(default_factory=ConnectionSettings)
    controller_colors: ControllerColorSettings = field(default_factory=ControllerColorSettings)
    input: InputSettings = field(default_factory=InputSettings)
    local_actions: LocalActions = field(default_factory=LocalActions)
    profiles: tuple[InputProfile, ...] = field(default_factory=lambda: (default_profile(),))

    @classmethod
    def default(cls) -> "AppSettings":
        """Return the built-in schema v1 settings snapshot."""
        return cls()

    def __post_init__(self) -> None:
        """Validate schema identity, nested settings, and profile selection."""
        if self.schema != SCHEMA:
            raise DomainValueError
        if not isinstance(self.active_profile, str) or not self.active_profile:
            raise DomainValueError
        if not isinstance(self.ui, UiSettings):
            raise DomainValueError
        if not isinstance(self.window, WindowSettings):
            raise DomainValueError
        if not isinstance(self.connection, ConnectionSettings):
            raise DomainValueError
        if not isinstance(self.controller_colors, ControllerColorSettings):
            raise DomainValueError
        if not isinstance(self.input, InputSettings):
            raise DomainValueError
        if not isinstance(self.local_actions, LocalActions):
            raise DomainValueError
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise DomainValueError
        if not all(isinstance(profile, InputProfile) for profile in self.profiles):
            raise DomainValueError
        profile_ids = [profile.id for profile in self.profiles]
        if len(profile_ids) != len(set(profile_ids)) or self.active_profile not in profile_ids:
            raise DomainValueError
