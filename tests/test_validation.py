"""tests/test_validation.py

Testes de streamlit_app/validation.py (US-2.2).
"""
from streamlit_app.validation import validate_upload

ALLOWED = ["png", "jpg", "jpeg", "webp"]


def test_empty_file_returns_warning_message():
    assert validate_upload(0, "image/png", 10, ALLOWED) == "O arquivo enviado está vazio."


def test_unsupported_type_returns_error_message():
    error = validate_upload(1000, "application/pdf", 10, ALLOWED)
    assert error is not None
    assert "não suportado" in error


def test_oversized_file_returns_error_with_sizes():
    ten_mb = 10 * 1024 * 1024
    error = validate_upload(ten_mb + 1, "image/png", 10, ALLOWED)
    assert error is not None
    assert "10MB" in error


def test_valid_png_returns_none():
    assert validate_upload(1000, "image/png", 10, ALLOWED) is None


def test_valid_jpg_mime_matches_jpeg_allowed_type():
    assert validate_upload(1000, "image/jpeg", 10, ALLOWED) is None


def test_jpeg_mime_matches_jpg_only_allowed_type():
    """Test that image/jpeg mime matches when only 'jpg' is in allowed_types.
    This isolates the jpg/jpeg normalization logic."""
    assert validate_upload(1000, "image/jpeg", 10, ["jpg"]) is None


def test_allowed_types_case_insensitive():
    """Test that uppercase allowed_types like 'PNG' or 'JPG' are handled correctly."""
    assert validate_upload(1000, "image/png", 10, ["PNG"]) is None
    assert validate_upload(1000, "image/jpeg", 10, ["JPG"]) is None
    assert validate_upload(1000, "image/png", 10, ["Png", "Jpg", "JPEG"]) is None
