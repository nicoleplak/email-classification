import hashlib

import pytest

from core.attachment_processor import AttachmentProcessor
from data import blob_output


def test_blob_attachment_is_read_and_hash_checked(monkeypatch):
    content = b"%PDF-1.7 synthetic"
    blobs = {"attachments/c/m/abc_file.pdf": content}
    monkeypatch.setattr(blob_output, "download", blobs.__getitem__)
    attachment = {
        "blob_name": "attachments/c/m/abc_file.pdf",
        "sha256": hashlib.sha256(content).hexdigest(),
    }

    assert AttachmentProcessor._get_content_bytes(attachment) == content

    blobs["attachments/c/m/abc_file.pdf"] = b"tampered"
    with pytest.raises(ValueError, match="SHA-256"):
        AttachmentProcessor._get_content_bytes(attachment)
