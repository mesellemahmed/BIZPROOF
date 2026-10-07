def get_field_registry(language: str | None) -> FieldRegistry:
    """Build (or return the cached) FieldRegistry for the given search language.

    Cached keyed by language, rebuilt on the same trigger register_tokenizers()
    uses (settings.SEARCH_LANGUAGE change). A fresh call with a new language
    builds and caches a new registry rather than mutating the old one.
    """
    if language in _registry_cache:
        return _registry_cache[language]

    text_analyzer = paperless_text_analyzer(language).analyze
    pattern_normalizer = _make_pattern_normalizer(language)

    specs = [
        dataclasses.replace(
            field,
            analyzer=_identity_analyzer
            if field.kind is FieldKind.KEYWORD
            else text_analyzer,
            pattern_normalizer=_fold_normalizer
            if field.kind is FieldKind.KEYWORD
            else pattern_normalizer,
        )
        for field in PUBLIC_FIELDS
    ]

    registry = FieldRegistry(specs)
    _registry_cache[language] = registry
    return registry
