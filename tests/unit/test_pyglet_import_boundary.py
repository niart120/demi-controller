import subprocess
import sys


def test_input_and_ui_modules_import_without_a_display() -> None:
    script = """
import sys

import demi.input.pyglet_backend
import demi.ui.controller_view
import demi.ui.window

display_modules = {"pyglet.window", "pyglet.graphics", "pyglet.text"}
loaded_display_modules = set(sys.modules) & display_modules
assert display_modules.isdisjoint(loaded_display_modules), sorted(loaded_display_modules)
"""

    result = subprocess.run(  # noqa: S603 - fixed interpreter and inline test script
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
