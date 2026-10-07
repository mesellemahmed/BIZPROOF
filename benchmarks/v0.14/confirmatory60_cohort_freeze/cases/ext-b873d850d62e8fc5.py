def page_published_signal_handler(instance, **kwargs):
    purge_pages_from_cache([instance])
