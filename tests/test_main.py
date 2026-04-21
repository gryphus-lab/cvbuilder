import pytest
import json
import sys
from pathlib import Path
from unittest.mock import patch
from main import run_parse, run_build_from_data, run_build_from_file, main

# --- Logic Function Tests ---


def test_run_parse_success(tmp_path):
    pdf_file = tmp_path / "test.pdf"
    pdf_file.touch()
    output_json = tmp_path / "output.json"

    mock_data = {"name": "Test User"}

    with (
        patch("main.parse_cv_to_json", return_value=mock_data) as mock_parser,
        patch("main.save_to_json") as mock_save,
    ):
        result = run_parse(pdf_file, output_json)

        assert result == mock_data
        mock_parser.assert_called_once_with(pdf_file)
        mock_save.assert_called_once_with(mock_data, output_json)


def test_run_parse_file_not_found():
    with pytest.raises(FileNotFoundError, match="PDF not found"):
        run_parse(Path("non_existent.pdf"))


def test_run_build_from_data(tmp_path):
    cv_data = {"name": "Test"}
    output_pdf = tmp_path / "cv.pdf"
    photo = tmp_path / "me.jpg"

    with patch("main.CVBuilder") as MockBuilder:
        instance = MockBuilder.return_value

        result = run_build_from_data(cv_data, output_pdf, photo)

        assert result == output_pdf
        instance.build.assert_called_once_with(cv_data, output_pdf, photo)


def test_run_build_from_file_success(tmp_path):
    json_path = tmp_path / "data.json"
    json_data = {"name": "John Doe"}
    json_path.write_text(json.dumps(json_data))
    output_pdf = tmp_path / "out.pdf"

    with patch("main.run_build_from_data") as mock_build_data:
        run_build_from_file(json_path, output_pdf)
        mock_build_data.assert_called_once_with(json_data, output_pdf, None)


def test_run_build_from_file_not_found():
    with pytest.raises(FileNotFoundError, match="JSON not found"):
        run_build_from_file(Path("missing.json"), Path("out.pdf"))


# --- CLI Entry Point Tests ---


def test_main_parse_command(tmp_path, capsys):
    pdf_path = tmp_path / "input.pdf"
    pdf_path.touch()
    output_path = tmp_path / "output.json"

    # Simulate: python main.py parse input.pdf -o output.json
    test_args = ["main.py", "parse", str(pdf_path), "-o", str(output_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_parse") as mock_run_parse,
    ):
        main()

        # Verify run_parse was called with resolved paths
        mock_run_parse.assert_called_once()
        captured = capsys.readouterr()
        assert "✅ JSON saved" in captured.out


def test_main_build_command(tmp_path, capsys):
    json_path = tmp_path / "input.json"
    json_path.touch()

    # Simulate: python main.py build --json input.json
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_build_from_file") as mock_run_build,
    ):
        main()

        mock_run_build.assert_called_once()
        captured = capsys.readouterr()
        assert "✅ PDF saved" in captured.out


def test_main_parse_error_exit():
    # Test that sys.exit(1) is called on FileNotFoundError
    test_args = ["main.py", "parse", "non_existent.pdf"]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_parse", side_effect=FileNotFoundError("Missing")),
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1


def test_main_build_json_error_exit(tmp_path):
    json_path = tmp_path / "bad.json"
    json_path.touch()
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch(
            "main.run_build_from_file",
            side_effect=json.JSONDecodeError("msg", "doc", 0),
        ),
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
