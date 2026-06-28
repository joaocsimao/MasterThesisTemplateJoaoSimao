#!/usr/bin/env python3
"""Print unique values from a CSV column.

Examples:
  python unique_values.py ASAP_2_Final_github_train.csv --column essay_set
  python unique_values.py ASAP_2_Final_github_train.csv --column 0
  python unique_values.py ASAP_2_Final_github_train.csv --column domain1_score --sorted

Notes:
- Column can be a header name (string) or a 0-based index.
- By default values are normalized with strip(); use --no-strip to keep raw values.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Optional


def _parse_column(value: str) -> str | int:
    value = value.strip()
    if value.isdigit():
        return int(value)
    return value


def _open_text(path: Path, encoding: str):
    # newline='' is recommended for csv module
    return path.open("r", encoding=encoding, newline="")


def iter_column_values(
    csv_path: Path,
    column: str | int,
    delimiter: str,
    encoding: str,
    strip_values: bool,
) -> Iterable[str]:
    with _open_text(csv_path, encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return  # empty file

        if isinstance(column, int):
            col_idx = column
            if col_idx < 0 or col_idx >= len(header):
                raise ValueError(
                    f"Column index {col_idx} is out of range for header length {len(header)}"
                )
        else:
            try:
                col_idx = header.index(column)
            except ValueError as e:
                preview = ", ".join(header[:15])
                if len(header) > 15:
                    preview += ", ..."
                raise ValueError(
                    f"Column name '{column}' not found. Header starts with: {preview}"
                ) from e

        for row_num, row in enumerate(reader, start=2):  # start=2 since header is row 1
            if col_idx >= len(row):
                # ragged rows: treat as empty
                raw = ""
            else:
                raw = row[col_idx]
            yield raw.strip() if strip_values else raw


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print unique values from a CSV column.",
    )
    parser.add_argument("csv", type=Path, help="Path to CSV file")
    parser.add_argument(
        "--column",
        required=True,
        type=_parse_column,
        help="Column header name OR 0-based index (e.g., essay_set OR 0)",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="CSV delimiter (default: ,)",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="File encoding (default: utf-8)",
    )
    parser.add_argument(
        "--sorted",
        action="store_true",
        help="Sort unique values before printing",
    )
    parser.add_argument(
        "--no-strip",
        dest="strip_values",
        action="store_false",
        help="Do not strip whitespace around values",
    )
    parser.add_argument(
        "--drop-empty",
        action="store_true",
        help="Exclude empty-string values from output",
    )

    args = parser.parse_args(argv)

    csv_path: Path = args.csv
    if not csv_path.exists():
        print(f"File not found: {csv_path}", file=sys.stderr)
        return 2

    try:
        uniques: set[str] = set(
            iter_column_values(
                csv_path=csv_path,
                column=args.column,
                delimiter=args.delimiter,
                encoding=args.encoding,
                strip_values=args.strip_values,
            )
        )
    except UnicodeDecodeError as e:
        print(
            f"Encoding error reading {csv_path} with encoding={args.encoding}: {e}",
            file=sys.stderr,
        )
        print("Tip: try --encoding latin-1", file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.drop_empty:
        uniques.discard("")

    values = sorted(uniques) if args.sorted else list(uniques)

    
    for v in values:
        print(v)
    print(f"Unique values: {len(values)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
