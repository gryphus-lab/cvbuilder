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


def test_main_parse_error_exit(tmp_path):
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


# --- Additional edge case and boundary tests ---


def test_run_build_from_data_no_photo(tmp_path):
    """Tests run_build_from_data with photo_path=None (the default)."""
    cv_data = {"name": "No Photo"}
    output_pdf = tmp_path / "cv.pdf"

    with patch("main.CVBuilder") as MockBuilder:
        instance = MockBuilder.return_value

        result = run_build_from_data(cv_data, output_pdf, None)

        assert result == output_pdf
        instance.build.assert_called_once_with(cv_data, output_pdf, None)


def test_run_build_from_file_with_photo(tmp_path):
    """Tests run_build_from_file passes photo_path through to run_build_from_data."""
    json_path = tmp_path / "data.json"
    json_data = {"name": "With Photo"}
    json_path.write_text(json.dumps(json_data))
    output_pdf = tmp_path / "out.pdf"
    photo_path = tmp_path / "photo.jpg"

    with patch("main.run_build_from_data") as mock_build_data:
        run_build_from_file(json_path, output_pdf, photo_path)
        mock_build_data.assert_called_once_with(json_data, output_pdf, photo_path)


def test_run_build_from_file_returns_output_path(tmp_path):
    """Tests that run_build_from_file returns the output_path value from run_build_from_data."""
    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps({"name": "Test"}))
    output_pdf = tmp_path / "out.pdf"

    with patch("main.run_build_from_data", return_value=output_pdf):
        result = run_build_from_file(json_path, output_pdf)
        assert result == output_pdf


def test_run_parse_uses_default_output_path(tmp_path):
    """Tests run_parse saves to default output path when none is specified."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.touch()
    mock_data = {"name": "Default Output"}

    with (
        patch("main.parse_cv_to_json", return_value=mock_data),
        patch("main.save_to_json") as mock_save,
    ):
        run_parse(pdf_file)
        # Default output is Path("results/cv_data.json")
        call_args = mock_save.call_args[0]
        assert str(call_args[1]) == "results/cv_data.json"


def test_main_parse_command_prints_parsing_message(tmp_path, capsys):
    """Tests that the parse command prints a 'Parsing' progress message to stdout."""
    pdf_path = tmp_path / "input.pdf"
    pdf_path.touch()
    output_path = tmp_path / "output.json"
    test_args = ["main.py", "parse", str(pdf_path), "-o", str(output_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_parse"),
    ):
        main()

    captured = capsys.readouterr()
    assert "🔄 Parsing" in captured.out
    assert str(pdf_path) in captured.out


def test_main_build_command_prints_building_message(tmp_path, capsys):
    """Tests that the build command prints a 'Building' progress message to stdout."""
    json_path = tmp_path / "input.json"
    json_path.touch()
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_build_from_file"),
    ):
        main()

    captured = capsys.readouterr()
    assert "🔄 Building PDF from" in captured.out
    assert str(json_path) in captured.out


def test_main_build_with_photo_argument(tmp_path, capsys):
    """Tests that the build command passes the --photo argument to run_build_from_file."""
    json_path = tmp_path / "input.json"
    json_path.touch()
    photo_path = tmp_path / "photo.jpg"
    test_args = [
        "main.py",
        "build",
        "--json",
        str(json_path),
        "--photo",
        str(photo_path),
    ]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_build_from_file") as mock_build,
    ):
        main()

    mock_build.assert_called_once()
    call_args = mock_build.call_args[0]
    # Third argument is photo_path
    assert call_args[2] == photo_path


def test_main_build_generic_error_exit(tmp_path):
    """Tests that a generic exception in build command exits with code 1."""
    json_path = tmp_path / "input.json"
    json_path.touch()
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_build_from_file", side_effect=RuntimeError("Unexpected error")),
    ):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1


def test_main_build_generic_error_prints_message(tmp_path, capsys):
    """Tests that a generic exception in build command prints an error message to stdout."""
    json_path = tmp_path / "input.json"
    json_path.touch()
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_build_from_file", side_effect=RuntimeError("Disk full")),
    ):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "❌ Build Error: Disk full" in captured.out


def test_main_parse_error_prints_message(tmp_path, capsys):
    """Tests that a parse exception prints the error detail to stdout."""
    test_args = ["main.py", "parse", "non_existent.pdf"]

    with (
        patch.object(sys, "argv", test_args),
        patch("main.run_parse", side_effect=ValueError("OCR engine missing")),
    ):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "❌ Parse Error: OCR engine missing" in captured.out


def test_main_build_json_error_prints_message(tmp_path, capsys):
    """Tests that a JSONDecodeError in build command prints 'Invalid JSON format' to stdout."""
    json_path = tmp_path / "bad.json"
    json_path.touch()
    test_args = ["main.py", "build", "--json", str(json_path)]

    with (
        patch.object(sys, "argv", test_args),
        patch(
            "main.run_build_from_file",
            side_effect=json.JSONDecodeError("Expecting value", "doc", 0),
        ),
    ):
        with pytest.raises(SystemExit):
            main()

    captured = capsys.readouterr()
    assert "Invalid JSON format" in captured.out


def test_run_build_from_data_returns_output_path(tmp_path):
    """Regression: run_build_from_data always returns the output_path regardless of photo."""
    cv_data = {"name": "Regression"}
    output_pdf = tmp_path / "cv_out.pdf"

    with patch("main.CVBuilder"):
        result = run_build_from_data(cv_data, output_pdf)
        assert result is output_pdf
