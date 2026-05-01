"""Tests for conftest.py fixtures changed in this PR."""

from pathlib import Path


def test_test_pdf_fixture_creates_file(test_pdf: Path):
    """test_pdf fixture must create a file that exists on disk."""
    assert test_pdf.exists()


def test_test_pdf_fixture_is_named_test_cv_pdf(test_pdf: Path):
    """test_pdf fixture must produce a file named 'test_cv.pdf'."""
    assert test_pdf.name == "test_cv.pdf"


def test_test_pdf_fixture_has_valid_pdf_header(test_pdf: Path):
    """test_pdf fixture must produce a file starting with the PDF magic bytes '%PDF-'."""
    content = test_pdf.read_bytes()
    assert content.startswith(b"%PDF-"), "File does not start with PDF magic bytes"


def test_test_pdf_fixture_is_not_empty(test_pdf: Path):
    """test_pdf fixture must produce a non-empty file."""
    assert test_pdf.stat().st_size > 0


def test_test_pdf_fixture_contains_eof_marker(test_pdf: Path):
    """test_pdf fixture must contain the PDF %%EOF trailer marker."""
    content = test_pdf.read_bytes()
    assert b"%%EOF" in content


def test_test_pdf_fixture_contains_xref_section(test_pdf: Path):
    """test_pdf fixture must contain an xref cross-reference table."""
    content = test_pdf.read_bytes()
    assert b"xref" in content


def test_test_pdf_fixture_contains_catalog_object(test_pdf: Path):
    """test_pdf fixture must include a PDF Catalog object referencing Pages."""
    content = test_pdf.read_bytes()
    assert b"/Catalog" in content
    assert b"/Pages" in content


def test_test_pdf_fixture_contains_page_object(test_pdf: Path):
    """test_pdf fixture must include at least one /Page object with a /MediaBox."""
    content = test_pdf.read_bytes()
    assert b"/Page" in content
    assert b"/MediaBox" in content


def test_test_pdf_fixture_is_function_scoped(tmp_path: Path, test_pdf: Path):
    """test_pdf fixture must reside inside the function-scoped tmp_path directory."""
    # tmp_path is unique per test function; test_pdf should be a child of it
    assert test_pdf.parent == tmp_path
