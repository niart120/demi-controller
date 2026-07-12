import importlib.metadata

import demi


def test_package_version_matches_metadata() -> None:
    assert demi.__version__ == importlib.metadata.version("demi-controller")
