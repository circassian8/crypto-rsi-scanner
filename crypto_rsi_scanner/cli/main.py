"""Compatibility CLI entrypoint.

Parser construction and command dispatch now live in ``crypto_rsi_scanner.cli``.
The command bodies still call the historical scanner helpers until each group is
extracted behind compatibility tests.
"""

from __future__ import annotations

from .dispatch import dispatch_args
from .parser import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch_args(args)


if __name__ == "__main__":
    main()
