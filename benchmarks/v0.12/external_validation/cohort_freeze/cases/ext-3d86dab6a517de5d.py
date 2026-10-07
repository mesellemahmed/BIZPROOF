def parse_ai_response(raw: dict) -> ClassificationSuggestions:
    """``raw`` is AIClient.run_llm_query()'s validated internal-shape result.
    This gives the rest of the module a named, typed boundary instead of
    passing the client's bare dict straight through everywhere.
    """

    def _choice(value: dict | None) -> TaxonomyChoiceDict:
        value = value or {}
        return TaxonomyChoiceDict(
            existing_ids=value.get("existing_ids", []),
            new_names=value.get("new_names", []),
        )

    return ClassificationSuggestions(
        title=raw.get("title", ""),
        tags=_choice(raw.get("tags")),
        correspondents=_choice(raw.get("correspondents")),
        document_types=_choice(raw.get("document_types")),
        storage_paths=_choice(raw.get("storage_paths")),
        dates=raw.get("dates", []),
    )
