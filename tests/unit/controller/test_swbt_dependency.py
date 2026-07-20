from importlib.metadata import version

from swbt import (
    AdapterInfo,
    Button,
    ControllerColors,
    DirectProController,
    DirectSwitchGamepad,
    IMUFrame,
    InputState,
    Stick,
    list_adapters,
)


def test_swbt_v04_direct_public_contract_is_available() -> None:
    """Expose the v0.4 Direct public values required by the Project_Demi boundary."""
    assert version("swbt-python").split(".")[:2] == ["0", "4"]
    assert all(
        value is not None
        for value in (
            AdapterInfo,
            Button,
            ControllerColors,
            DirectProController,
            DirectSwitchGamepad,
            IMUFrame,
            InputState,
            Stick,
            list_adapters,
        )
    )
