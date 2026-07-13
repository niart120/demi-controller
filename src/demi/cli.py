"""Command line entry point for Project_Demi."""

import sys
from collections.abc import Sequence

from demi import __version__


def run_application() -> int:
    """Load and run the GUI only for an argument-free CLI invocation.

    Returns:
        Process exit status from the desktop application.
    """
    from demi.app import run_application as application_runner  # noqa: PLC0415

    return application_runner()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: Arguments excluding the executable name. If omitted, arguments
            are read from ``sys.argv``.

    Returns:
        The process exit status.
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"] or arguments == ["-V"]:
        sys.stdout.write(f"{__version__}\n")
        return 0
    if arguments:
        sys.stderr.write(f"unknown argument: {arguments[0]}\n")
        return 2

    return run_application()
