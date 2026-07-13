MAGIC: dict[bytes, str] = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def sniff_content_type(data: bytes) -> str | None:
    """Detect type from magic bytes. A file named 'invoice.pdf' full of
    HTML is a classic attack; we trust the bytes, not the name."""
    for signature, content_type in MAGIC.items():
        if data.startswith(signature):
            return content_type
    return None