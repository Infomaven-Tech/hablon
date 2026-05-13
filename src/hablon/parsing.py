from __future__ import annotations

import argparse
import shlex


class ParseError(Exception):
    pass


class _NoExitParser(argparse.ArgumentParser):
    def error(self, message: str):
        raise ParseError(message)


def make_parser(prog: str, description: str = "") -> _NoExitParser:
    return _NoExitParser(prog=prog, description=description, add_help=False, exit_on_error=False)


def split_args(line: str) -> list[str]:
    line = line.strip()
    if not line:
        return []
    try:
        return shlex.split(line, posix=True)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc


def decode_nl(s: str) -> str:
    """Decode literal backslash-n into a real newline so users can pass
    multi-line notes inline as `--notes "a\\nb"`.
    """
    return s.replace("\\n", "\n")
