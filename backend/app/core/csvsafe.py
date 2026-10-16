"""CSV downloads that a spreadsheet opens as plain data, never as formulas."""

import csv
import io
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def cell(value: Any) -> Any:
    # A spreadsheet runs a cell that starts like a formula; the quote makes it plain text.
    return f"'{value}" if isinstance(value, str) and value.startswith(FORMULA_START) else value


def stream(columns: Sequence[str], rows: Iterable[dict[str, Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for line in (columns, *([cell(r[c]) for c in columns] for r in rows)):
        writer.writerow(line)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
