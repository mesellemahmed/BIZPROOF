    def set_as_homepage(self, user=None):
        """
        Sets the given page as the homepage.
        Updates the url paths for all affected pages.
        Returns the old home page (if any).
        """
        if user:
            changed_by = get_clean_username(user)
        else:
            changed_by = constants.SCRIPT_USERNAME

        changed_date = now()

        try:
            old_home = self.__class__.objects.get(
                is_home=True,
                site=self.site_id,
            )
        except self.__class__.DoesNotExist:
            _lock_tree_roots(self)
            old_home_tree = []
        else:
            _lock_tree_roots(self, old_home)

            old_home.update(
                is_home=False,
                changed_by=changed_by,
                changed_date=changed_date,
            )
            old_home_tree = old_home._set_title_root_path()

        self.update(
            is_home=True,
            changed_by=changed_by,
            changed_date=changed_date,
        )
        new_home_tree = self._remove_title_root_path()
        return (new_home_tree, old_home_tree)
