from importlib.metadata import version

from swbt import (
    AdapterInfo,
    Button,
    ControllerColors,
    IMUFrame,
    InputState,
    ProController,
    Stick,
    list_adapters,
)


def test_swbt_v03_public_contract_is_available() -> None:
    """Expose the v0.3 public values required by the Project_Demi boundary."""
    assert version("swbt-python").split(".")[:2] == ["0", "3"]
    assert all(
        value is not None
        for value in (
            AdapterInfo,
            Button,
            ControllerColors,
            IMUFrame,
            InputState,
            ProController,
            Stick,
            list_adapters,
        )
    )
