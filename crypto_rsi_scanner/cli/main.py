"""Compatibility CLI entrypoint.

Runtime dispatch still lives in :mod:`crypto_rsi_scanner.scanner` during this
incremental consolidation pass. New CLI modules provide stable package
boundaries for future command-group extraction.
"""

from __future__ import annotations


def main() -> None:
    from .. import scanner

    scanner.cli()


if __name__ == "__main__":
    main()
