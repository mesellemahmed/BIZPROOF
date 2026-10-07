def add_or_update_document_in_llm_index(sender, document, **kwargs):
    """
    Add or update a document in the LLM index when it is created or updated.
    """
    if kwargs.get("skip_ai_index"):
        return
    ai_config = AIConfig()
    if ai_config.llm_index_enabled:
        from documents.tasks import update_document_in_llm_index

        update_document_in_llm_index.apply_async(kwargs={"document": document})
