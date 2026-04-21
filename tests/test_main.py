import unittest
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import main as cli_main

class TestMainCLI(unittest.TestCase):
    def test_parse_exits_when_pdf_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_pdf = Path(tmp_dir) / "missing.pdf"
            with patch.object(sys, "argv", ["main.py", "parse", str(missing_pdf)]):
                with patch("builtins.print") as mock_print:
                    with self.assertRaises(SystemExit):
                        cli_main.main()
                    mock_print.assert_any_call(f"❌ Error: PDF not found: {missing_pdf.resolve()}")

    def test_build_success_calls_logic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            json_path = tmp_path / "data.json"
            out_path = tmp_path / "out.pdf"
            json_path.touch() # Create dummy file

            with patch.object(sys, "argv", ["main.py", "build", "--json", str(json_path), "--output", str(out_path)]):
                with patch("main.run_build_from_file") as mock_build:
                    cli_main.main()
                    mock_build.assert_called_once()

if __name__ == "__main__":
    unittest.main()
