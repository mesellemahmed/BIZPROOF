    def get_patterns(self) -> list[URLResolver]:
        self.discover_plugins()

        # We want untranslated name of the plugin for its slug so we deactivate translation
        lang = get_language()
        deactivate_all()

        try:
            url_patterns = []
            for plugin in self.registered_plugins:
                p = plugin()
                slug = slugify(force_str(normalize_name(p.__class__.__name__)))
                url_patterns += [
                    re_path(rf"^plugin/{slug}/", include(p.plugin_urls)),
                ]
        finally:
            # Reactivate translation
            activate(lang)

        return url_patterns
