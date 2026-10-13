import io

from app.config import settings
from app.services import document_storage


class FakeS3:
    def __init__(self, response=None):
        self.upload_calls = []
        self.response = response or {"Body": io.BytesIO(b"%PDF-1.7"), "ContentType": "application/pdf"}
        self.get_calls = []

    def upload_file(self, path, bucket, key, ExtraArgs):
        self.upload_calls.append((path, bucket, key, ExtraArgs))

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        return self.response


def test_document_filename_accepts_only_generated_logical_upload_urls():
    assert document_storage.document_filename("/uploads/" + "a" * 32 + ".pdf") == "a" * 32 + ".pdf"
    assert document_storage.document_filename("/uploads/../../etc/passwd") is None
    assert document_storage.document_filename("https://example.invalid/file.pdf") is None
    assert document_storage.document_filename("/uploads/" + "a" * 32 + ".html") is None


def test_s3_upload_uses_private_bucket_key_and_content_type(tmp_path, monkeypatch):
    path = tmp_path / "document.pdf"
    path.write_bytes(b"%PDF-1.7")
    filename = "b" * 32 + ".pdf"
    client = FakeS3()

    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "private-documents")
    monkeypatch.setattr(settings, "S3_KEY_PREFIX", "mentorlink-private")
    monkeypatch.setattr(document_storage, "_s3_client", lambda: client)

    document_storage.upload_document(str(path), filename, "application/pdf")

    assert client.upload_calls == [(
        str(path),
        "private-documents",
        "mentorlink-private/" + filename,
        {"ContentType": "application/pdf", "ContentDisposition": "inline"},
    )]


def test_s3_read_never_builds_a_public_url_and_closes_response_body(monkeypatch):
    body = io.BytesIO(b"%PDF-1.7")
    client = FakeS3({"Body": body, "ContentType": "application/pdf"})
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(settings, "S3_BUCKET", "private-documents")
    monkeypatch.setattr(settings, "S3_KEY_PREFIX", "mentorlink-private")
    monkeypatch.setattr(document_storage, "_s3_client", lambda: client)

    data, content_type = document_storage.read_private_document("c" * 32 + ".pdf")

    assert data == b"%PDF-1.7"
    assert content_type == "application/pdf"
    assert client.get_calls == [{
        "Bucket": "private-documents",
        "Key": "mentorlink-private/" + "c" * 32 + ".pdf",
    }]
    assert body.closed
