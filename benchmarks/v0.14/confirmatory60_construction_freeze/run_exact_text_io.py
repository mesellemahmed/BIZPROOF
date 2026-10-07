from __future__ import annotations

import runpy
import sys
from pathlib import Path
from typing import Any


if len(sys.argv) < 2:
    raise SystemExit(
        "usage: run_exact_text_io.py "
        "<builder.py> [builder arguments...]"
    )


builder = sys.argv[1]

forwarded = [
    builder,
    *sys.argv[2:],
]


original_open = Path.open


def exact_open(
    self: Path,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
) -> Any:
    if (
        "b" not in mode
        and any(
            marker in mode
            for marker in (
                "w",
                "a",
                "x",
            )
        )
    ):
        # Disable Windows newline translation.
        newline = ""

    return original_open(
        self,
        mode=mode,
        buffering=buffering,
        encoding=encoding,
        errors=errors,
        newline=newline,
    )


Path.open = exact_open  # type: ignore[method-assign]

sys.argv = forwarded

runpy.run_path(
    builder,
    run_name="__main__",
)
