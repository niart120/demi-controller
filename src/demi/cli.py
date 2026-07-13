"""Command line entry point for Project_Demi."""

import sys
from collections.abc import Sequence

from demi import __version__


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

    from demi.app import run_application  # noqa: PLC0415 - GUI起動時までapplicationをimportしない。

    return run_application()
