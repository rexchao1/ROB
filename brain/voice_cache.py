"""The fixed script is the only speech kept in the live voice's disk cache."""

from functools import cache


@cache
def fixed_keys() -> frozenset[str]:
    """Snapshot the recording script once; later conversation never adds lines."""
    from brain.lines import fixed_lines
    from brain.voice import line_key

    return frozenset(line_key(line) for line in fixed_lines())
