    def _append_i18n_patterns(text, items):
        """Append ``urlpatterns += i18n_patterns(...)`` with ``items`` to the module.

        A new block is added at the end of the file (after any existing
        ``i18n_patterns`` call) so the CMS catch-all stays last. The
        ``i18n_patterns`` import is assumed present -- this is only called when
        the module already uses it.
        """
        if not text.endswith("\n"):
            text += "\n"
        lines = "\n".join(f"    {item}," for item in items)
        block = "\n# django CMS URLs (added by `djangocms .`)\nurlpatterns += i18n_patterns(\n" + lines + "\n)\n"
        return text + block, list(items)
