def register_admin_urls():
    snippet_index_patterns = (
        [
            path("", snippet_views.ModelIndexView.as_view(), name="index"),
        ],
        "wagtailsnippets",
    )

    return [
        path("snippets/", include(snippet_index_patterns)),
    ]
