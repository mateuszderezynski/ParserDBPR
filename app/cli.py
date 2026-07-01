"""Command line entry point for DBPR text export."""

import argparse
import sys
from pathlib import Path

from app.dbpr_parser import DbprParseError, parse_dbpr
from app.text_export import render_equipment_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dbpr-to-txt",
        description="Extract a simple gear list from a .dbpr file.",
    )
    parser.add_argument("dbpr_file", type=Path, help="Path to the .dbpr file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .txt path. If omitted, text is printed to stdout.",
    )
    parser.add_argument(
        "--project-name",
        help="Project name to print in the text output.",
    )
    args = parser.parse_args(argv)

    try:
        data = parse_dbpr(args.dbpr_file)
    except DbprParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    project_name = args.project_name or args.dbpr_file.stem
    text = render_equipment_text(data, project_name)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
