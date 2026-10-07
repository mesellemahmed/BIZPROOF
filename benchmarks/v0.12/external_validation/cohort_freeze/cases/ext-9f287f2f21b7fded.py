def bytes_to_sanitized_message(self, data: bytes) -> EmailMessage:
    m = email.message_from_bytes(data, policy=email.policy.SMTP)
    if m.is_multipart():
        parts = m.get_payload()
        # If is_multipart=True then get_payload() returns list[Message].
        # Mypy does not know this, hence the assert.
        assert isinstance(parts, list)
        # use list() here so we don't mutate the same list we're iterating
        for part in list(parts):
            if part.get_content_type() == "message/rfc822":
                # Drop message/rfc822 parts to avoid recursion issues with
                # deep attachment-within-attachment stacks.
                parts.remove(part)
            if part.get_content_maintype() == "text":
                # Call set_content to force correct content-transfer-encoding
                # selection and line wrapping
                part.set_content(part.get_content())
    else:
        # Call set_content to force correct content-transfer-encoding
        # selection and line wrapping
        m.set_content(m.get_content())
    return m
