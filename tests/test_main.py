"""
Tests for the CLI entry points in main.py.

These tests cover the parse/build subcommands with success and failure paths
while mocking heavy dependencies and filesystem side effects where possible.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as cli_main


class TestMainCLIParse(unittest.TestCase):
    def test_parse_exits_when_pdf_is_missing(self):
        missing_pdf = Path("/tmp/definitely-missing-cvbuilder-input.pdf")

        with patch.object(sys, "argv", ["main.py", "parse", str(missing_pdf)]):
            with patch("builtins.print") as mock_print:
                with self.assertRaises(SystemExit) as exc:
                    cli_main.main()

        self.assertEqual(exc.exception.code, 1)
        mock_print.assert_any_call(f"❌ PDF not found: {missing_pdf.resolve()}")

    def test_parse_success_calls_parser_and_saves_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_path = tmp_path / "input.pdf"
            output_path = tmp_path / "cv_data.json"
            pdf_path.touch()

            parsed_data = {"profile": "Sample profile"}

            with patch.object(
                sys, "argv", ["main.py", "parse", str(pdf_path), "-o", str(output_path)]
            ):
                with patch(
                    "main.parse_cv_to_json", return_value=parsed_data
                ) as mock_parse:
                    with patch("main.save_to_json") as mock_save:
                        with patch("builtins.print") as mock_print:
                            cli_main.main()

            mock_parse.assert_called_once_with(pdf_path.resolve())
            mock_save.assert_called_once_with(parsed_data, output_path)
            mock_print.assert_any_call(f"🔄 Parsing {pdf_path.name}...")
            mock_print.assert_any_call(f"✅ JSON saved → {output_path}")


class TestMainCLIBuild(unittest.TestCase):
    def test_build_exits_when_json_is_missing(self):
        missing_json = Path("/tmp/definitely-missing-cvbuilder-input.json")

        with patch.object(
            sys, "argv", ["main.py", "build", "--json", str(missing_json)]
        ):
            with patch("builtins.print") as mock_print:
                with self.assertRaises(SystemExit) as exc:
                    cli_main.main()

        self.assertEqual(exc.exception.code, 1)
        mock_print.assert_any_call(f"❌ JSON not found: {missing_json.resolve()}")
        mock_print.assert_any_call("   Run: python main.py parse   first")

    def test_build_success_loads_json_and_calls_builder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            json_path = tmp_path / "cv_data.json"
            output_path = tmp_path / "cv_updated.pdf"
            photo_path = tmp_path / "photo.jpg"

            cv_data = {"personal_info": {"name": "Test User"}}
            json_path.write_text(json.dumps(cv_data), encoding="utf-8")

            with patch.object(
                sys,
                "argv",
                [
                    "main.py",
                    "build",
                    "--json",
                    str(json_path),
                    "--output",
                    str(output_path),
                    "--photo",
                    str(photo_path),
                ],
            ):
                with patch("main.CVBuilder") as mock_builder_cls:
                    with patch("builtins.print") as mock_print:
                        cli_main.main()

            mock_builder_cls.assert_called_once_with()
            mock_builder_cls.return_value.build.assert_called_once_with(
                cv_data, output_path, photo_path
            )
            mock_print.assert_any_call(f"🔄 Building PDF from {json_path.name}...")


if __name__ == "__main__":
    unittest.main()
