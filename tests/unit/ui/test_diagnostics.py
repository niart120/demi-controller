from demi.input.relative_pointer import RelativePointerCapability, RelativePointerQuality
from demi.ui.diagnostics import collect_support_diagnostics


def test_support_diagnostics_include_only_safe_runtime_identifiers() -> None:
    versions = {
        "swbt-python": "0.3.4",
    }

    snapshot = collect_support_diagnostics(
        RelativePointerCapability(RelativePointerQuality.RAW_UNACCELERATED),
        demi_version="0.1.0",
        os_name=lambda: "Windows",
        os_release=lambda: "11",
        python_version=lambda: "3.12.10",
        distribution_version=versions.__getitem__,
        pyside6_version="6.11.0",
        qt_version="6.11.0",
    )

    assert snapshot.os_name == "Windows"
    assert snapshot.os_release == "11"
    assert snapshot.python_version == "3.12.10"
    assert snapshot.demi_version == "0.1.0"
    assert snapshot.swbt_version == "0.3.4"
    assert snapshot.pyside6_version == "6.11.0"
    assert snapshot.qt_version == "6.11.0"
    assert snapshot.pointer_quality is RelativePointerQuality.RAW_UNACCELERATED
    assert snapshot.log_message == (
        "support diagnostics os=Windows 11 python=3.12.10 demi=0.1.0 "
        "swbt=0.3.4 pyside6=6.11.0 qt=6.11.0 pointer=raw_unaccelerated"
    )
    assert "bond" not in snapshot.log_message
    assert "pyglet" not in snapshot.log_message
