"""Safe support diagnostics for the Qt desktop boundary."""

from __future__ import annotations

import platform
from dataclasses import dataclass
from importlib.metadata import version
from typing import TYPE_CHECKING

import PySide6
from PySide6.QtCore import qVersion

import demi

if TYPE_CHECKING:
    from collections.abc import Callable

    from demi.input.relative_pointer import RelativePointerCapability, RelativePointerQuality


@dataclass(frozen=True, slots=True)
class SupportDiagnostics:
    """Safe runtime identifiers useful for support reports.

    Attributes:
        os_name: Operating-system family.
        os_release: Operating-system release string.
        python_version: Running Python version.
        demi_version: Installed Project_Demi version.
        swbt_version: Installed swbt-python version.
        pyside6_version: Installed PySide6 version.
        qt_version: Linked Qt version.
        pointer_quality: Declared relative-pointer capability.
    """

    os_name: str
    os_release: str
    python_version: str
    demi_version: str
    swbt_version: str
    pyside6_version: str
    qt_version: str
    pointer_quality: RelativePointerQuality

    @property
    def log_message(self) -> str:
        """Return a secret-free, single-line support log record."""
        return (
            f"support diagnostics os={self.os_name} {self.os_release} "
            f"python={self.python_version} demi={self.demi_version} "
            f"swbt={self.swbt_version} pyside6={self.pyside6_version} "
            f"qt={self.qt_version} pointer={self.pointer_quality.value}"
        )


def collect_support_diagnostics(
    pointer_capability: RelativePointerCapability,
    *,
    demi_version: str = demi.__version__,
    os_name: Callable[[], str] = platform.system,
    os_release: Callable[[], str] = platform.release,
    python_version: Callable[[], str] = platform.python_version,
    distribution_version: Callable[[str], str] = version,
    pyside6_version: str | None = None,
    qt_version: str | None = None,
) -> SupportDiagnostics:
    """Collect the allow-listed desktop runtime identifiers.

    Args:
        pointer_capability: Active relative-pointer capability selected by the UI.
        demi_version: Installed Project_Demi version.
        os_name: Reads the operating-system family.
        os_release: Reads the operating-system release.
        python_version: Reads the Python version.
        distribution_version: Looks up an installed distribution version.
        pyside6_version: Optional injected PySide6 version for tests.
        qt_version: Optional injected Qt version for tests.

    Returns:
        A snapshot containing only safe support identifiers.
    """
    return SupportDiagnostics(
        os_name=os_name(),
        os_release=os_release(),
        python_version=python_version(),
        demi_version=demi_version,
        swbt_version=distribution_version("swbt-python"),
        pyside6_version=PySide6.__version__ if pyside6_version is None else pyside6_version,
        qt_version=qVersion() if qt_version is None else qt_version,
        pointer_quality=pointer_capability.quality,
    )
