"""
Entry point for Easy Localhost.
"""

from __future__ import annotations

import logging

from app import EasyLocalhostApp


def configure_logging() -> None:
    """Keep logging local and low-noise for desktop usage."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    configure_logging()
    app = EasyLocalhostApp()
    app.mainloop()


if __name__ == "__main__":
    main()
