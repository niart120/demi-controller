import inspect
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


def test_swbt_v05_direct_public_contract_is_available() -> None:
    """Expose the v0.5 Direct public values required by the Project_Demi boundary."""
    installed_version = tuple(int(part) for part in version("swbt-python").split(".")[:3])
    assert (0, 5, 1) <= installed_version < (0, 6, 0)
    constructor_parameters = inspect.signature(DirectProController).parameters
    profile_parameters = inspect.signature(DirectProController.create_profile).parameters
    assert "profile_path" in constructor_parameters
    assert "key_store_path" not in constructor_parameters
    assert {
        "adapter",
        "profile_path",
        "local_address",
        "pair_timeout",
        "controller_colors",
    } <= set(profile_parameters)
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
