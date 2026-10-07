def is_export_storage_configured() -> bool:
    """Return whether exports can be uploaded and shared by link.

    Both a bucket and a backend are required; the task cannot upload without
    either, so a partial ``EXPORT_STORAGE`` falls back to direct downloads.
    """
    storage_config = current_app.config["EXPORT_STORAGE"]
    has_bucket = bool(storage_config.get("bucket"))
    has_backend = storage_config.get("backend") is not None
    if has_bucket != has_backend:
        _warn_partial_storage("backend" if has_bucket else "bucket")
    return has_bucket and has_backend
