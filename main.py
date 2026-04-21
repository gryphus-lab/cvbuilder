#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from src.parser import parse_cv_to_json, save_to_json
from src.builder import CVBuilder

# --- LOGIC FUNCTIONS (Exportable) ---


def run_parse(pdf_path: Path, output_path: Path = Path("results/cv_data.json")):
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    cv_data = parse_cv_to_json(pdf_path)
    save_to_json(cv_data, output_path)
    return cv_data


# Inside main.py


def run_build_from_data(cv_data: dict, output_path: Path, photo_path: Path = None):
    builder = CVBuilder()
    # This calls your CVBuilder.build() method provided in your snippet
    builder.build(cv_data, output_path, photo_path)
    return output_path


# --- CLI ENTRY POINT ---


def main() -> None:
    parser = argparse.ArgumentParser(description="CV Parser & Builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # PARSE
    parse_p = subparsers.add_parser("parse", help="Parse PDF → JSON")
    parse_p.add_argument(
        "pdf_path", nargs="?", type=Path, default=Path("resources/cv_original.pdf")
    )
    parse_p.add_argument(
        "-o", "--output", type=Path, default=Path("results/cv_data.json")
    )

    # BUILD
    build_p = subparsers.add_parser("build", help="Build PDF from JSON")
    build_p.add_argument("--json", type=Path, default=Path("results/cv_data.json"))
    build_p.add_argument("--photo", type=Path)
    build_p.add_argument("--output", type=Path, default=Path("results/cv_updated.pdf"))

    args = parser.parse_args()

    try:
        if args.command == "parse":
            print(f"🔄 Parsing {args.pdf_path}...")
            run_parse(args.pdf_path.resolve(), args.output)
            print(f"✅ JSON saved → {args.output}")
        elif args.command == "build":
            print(f"🔄 Building PDF from {args.json}...")
            run_build_from_data(args.json.resolve(), args.output, args.photo)
            print(f"✅ PDF saved → {args.output}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
