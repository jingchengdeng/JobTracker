import pytest
from src.services.text_extract import extract_text


def test_extract_text_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("/fake/path.txt")


def test_extract_text_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text("/nonexistent/file.pdf")
