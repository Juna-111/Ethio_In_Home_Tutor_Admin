import os
import re
from typing import Optional

from app.config import UPLOAD_DIR, settings

_FILENAME_RE = re.compile(r"[0-9a-f]{32}\.(?:pdf|png|jpe?g)\Z", re.IGNORECASE)
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def document_filename(document_url: Optional[str]) -> Optional[str]:
    """Accept only the application's generated logical upload URLs."""
    if not isinstance(document_url, str) or not document_url.startswith("/uploads/"):
        return None
    filename = document_url[len("/uploads/"):]
    if "/" in filename or "\\" in filename or not _FILENAME_RE.fullmatch(filename):
        return None
    return filename


def local_document_path(filename: str, upload_dir: str = UPLOAD_DIR) -> Optional[str]:
    if not _FILENAME_RE.fullmatch(filename or ""):
        return None
    root = os.path.realpath(upload_dir)
    path = os.path.realpath(os.path.join(root, filename))
    try:
        if os.path.commonpath((root, path)) != root:
            return None
    except ValueError:
        return None
    return path


def content_type_for(filename: str) -> str:
    return _CONTENT_TYPES.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")


def _object_key(filename: str) -> str:
    prefix = (settings.S3_KEY_PREFIX or "").strip("/")
    return f"{prefix}/{filename}" if prefix else filename


def _s3_client():
    # Imported lazily so local-only development does not initialize cloud clients.
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
    )


def upload_document(local_path: str, filename: str, content_type: Optional[str] = None) -> None:
    """Upload privately to S3/R2 when configured; local mode keeps the file in UPLOAD_DIR."""
    if settings.DOCUMENT_STORAGE_BACKEND != "s3":
        return
    safe_name = document_filename(f"/uploads/{filename}")
    if safe_name is None:
        raise ValueError("Invalid generated document filename.")
    _s3_client().upload_file(
        local_path,
        settings.S3_BUCKET,
        _object_key(safe_name),
        ExtraArgs={
            "ContentType": content_type or content_type_for(safe_name),
            "ContentDisposition": "inline",
        },
    )


def read_private_document(filename: str) -> tuple[bytes, str]:
    """Read an object without ever exposing a public object URL or presigned link."""
    safe_name = document_filename(f"/uploads/{filename}")
    if safe_name is None:
        raise ValueError("Invalid generated document filename.")
    if settings.DOCUMENT_STORAGE_BACKEND != "s3":
        path = local_document_path(safe_name)
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(safe_name)
        with open(path, "rb") as file:
            return file.read(), content_type_for(safe_name)

    response = _s3_client().get_object(Bucket=settings.S3_BUCKET, Key=_object_key(safe_name))
    body = response["Body"]
    try:
        data = body.read()
    finally:
        body.close()
    return data, response.get("ContentType") or content_type_for(safe_name)
