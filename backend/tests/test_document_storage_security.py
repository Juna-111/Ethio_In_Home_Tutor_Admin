import os

import pytest

from app.routes.admin import _resolve_uploaded_document_path
from app.routes.tutors import _validate_magic_bytes


def test_document_path_accepts_only_generated_upload_url(tmp_path):
    filename = "a" * 32 + ".pdf"
    expected = os.path.realpath(tmp_path / filename)

    assert _resolve_uploaded_document_path(f"/uploads/{filename}", str(tmp_path)) == expected


@pytest.mark.parametrize(
    "document_url",
    [
        "/uploads/../../etc/passwd",
        "/uploads/..%2f..%2fetc/passwd",
        "/uploads/subdir/" + "a" * 32 + ".pdf",
        "/uploads/" + "a" * 32 + ".html",
        "https://example.invalid/private.pdf",
        "/uploads/C:\\Windows\\win.ini",
        "/uploads/" + "a" * 31 + ".pdf",
    ],
)
def test_document_path_rejects_untrusted_or_non_generated_urls(tmp_path, document_url):
    assert _resolve_uploaded_document_path(document_url, str(tmp_path)) is None


@pytest.mark.parametrize(
    ("extension", "header"),
    [
        (".pdf", b"%PDF-1.7"),
        (".png", b"\x89PNG\r\n\x1a\nrest"),
        (".jpg", b"\xff\xd8\xffrest"),
        (".jpeg", b"\xff\xd8\xffrest"),
    ],
)
def test_upload_signature_must_match_extension(extension, header):
    assert _validate_magic_bytes(header, extension)


def test_upload_signature_rejects_mismatched_extension():
    assert not _validate_magic_bytes(b"%PDF-1.7", ".png")
    assert not _validate_magic_bytes(b"\x89PNG\r\n\x1a\nrest", ".pdf")
    assert not _validate_magic_bytes(b"plain text", ".jpg")
