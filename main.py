#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from src.parser import parse_cv_to_json, save_to_json
from src.builder import CVBuilder

# --- LOGIC FUNCTIONS ---

def run_parse(pdf_path: Path, output_path: Path = Path("results/cv_data.json")):
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    cv_data = parse_cv_to_json(pdf_path)
    save_to_json(cv_data, output_path)
    return cv_data

def run_build_from_data(cv_data: dict, output_path: Path, photo_path: Path = None):
    builder = CVBuilder()
    builder.build(cv_data, output_path, photo_path)
    return output_path

def run_build_from_file(json_path: Path, output_path: Path, photo_path: Path = None):
    if not json_path.exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return run_build_from_data(data, output_path, photo_path)

# --- CLI ---

def main() -> None:
    parser = argparse.ArgumentParser(description="CV Parser & Builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_p = subparsers.add_parser("parse")
    parse_p.add_argument("pdf_path", nargs="?", type=Path, default=Path("resources/cv_original.pdf"))
    parse_p.add_argument("-o", "--output", type=Path, default=Path("results/cv_data.json"))

    build_p = subparsers.add_parser("build")
    build_p.add_argument("--json", type=Path, default=Path("results/cv_data.json"))
    build_p.add_argument("--photo", type=Path)
    build_p.add_argument("--output", type=Path, default=Path("results/cv_updated.pdf"))

    args = parser.parse_args()

    if args.command == "parse":
        try:
            print(f"🔄 Parsing {args.pdf_path}...")
            run_parse(args.pdf_path.resolve(), args.output)
            print(f"✅ JSON saved → {args.output}")
        except FileNotFoundError as e:
            print(f"❌ Parse Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    elif args.command == "build":
        try:
            print(f"🔄 Building PDF from {args.json}...")
            run_build_from_file(args.json.resolve(), args.output, args.photo)
            print(f"✅ PDF saved → {args.output}")
        except FileNotFoundError as e:
            print(f"❌ Build Error: JSON file not found: {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Build Error: Invalid JSON format: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()