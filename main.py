#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

from src.parser import parse_cv_to_json, save_to_json
from src.builder import CVBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="CV Parser & Builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ====================== PARSE ======================
    parse_p = subparsers.add_parser("parse", help="Parse PDF → JSON")
    parse_p.add_argument(
        "pdf_path",
        nargs="?",
        type=Path,
        default=Path("resources/cv_original.pdf"),
        help="Path to CV PDF",
    )
    parse_p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results/cv_data.json"),
        help="Output JSON",
    )

    # ====================== BUILD ======================
    build_p = subparsers.add_parser("build", help="Build PDF from JSON")
    build_p.add_argument(
        "--json",
        type=Path,
        default=Path("results/cv_data.json"),
        help="Input JSON file (default: results/cv_data.json)",
    )

    build_p.add_argument(
        "--photo",
        nargs="?",
        type=Path,
        help="Path to your profile photo (JPG/PNG)",
    )

    build_p.add_argument(
        "--output",
        type=Path,
        default=Path("results/cv_updated.pdf"),
        help="Output PDF path",
    )

    args = parser.parse_args()

    if args.command == "parse":
        pdf_file = args.pdf_path.resolve()
        if not pdf_file.exists():
            print(f"❌ PDF not found: {pdf_file}")
            sys.exit(1)

        print(f"🔄 Parsing {pdf_file.name}...")
        cv_data = parse_cv_to_json(pdf_file)
        save_to_json(cv_data, args.output)
        print(f"✅ JSON saved → {args.output}")

    elif args.command == "build":
        json_file = args.json.resolve()
        if not json_file.exists():
            print(f"❌ JSON not found: {json_file}")
            print("   Run: python main.py parse   first")
            sys.exit(1)

        print(f"🔄 Building PDF from {json_file.name}...")
        with open(json_file, encoding="utf-8") as f:
            cv_data = json.load(f)

        builder = CVBuilder()
        builder.build(cv_data, args.output, args.photo)


if __name__ == "__main__":
    main()
