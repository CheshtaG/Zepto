import logging
import sys


def configure_logging() -> None:
    """Configure application-wide structured logging."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g. by uvicorn); don't duplicate handlers.
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(handler)

