    def _is_active(self):
        """ To be considered active, a menu should either:

        - have its URL matching the request's URL and have no children
        - or have a children menu URL matching the request's URL

        Matching an URL means, either:

        - be equal, eg ``/contact/on-site`` vs ``/contact/on-site``
        - be equal after unslug, eg ``/shop/1`` and ``/shop/my-super-product-1``

        Note that saving a menu URL with an anchor or a query string is
        considered a corner case, and the following applies:

        - anchor/fragment are ignored during the comparison (it would be
          impossible to compare anyway as the client is not sending the anchor
          to the server as per RFC)
        - query string parameters should be the same to be considered equal, as
          those could drasticaly alter a page result
        """
        if not request or self.is_mega_menu:
            # There is no notion of `active` if we don't have a request to
            # compare the url to.
            # Also, mega menu are never considered active.
            return False

        request_url = url_parse(request.httprequest.url)

        if not self.child_id:
            menu_url = url_parse(self._clean_url())
            unslug_url = self.env['ir.http']._unslug_url
            if unslug_url(menu_url.path) == unslug_url(request_url.path):
                # By default we compare the unslug version of the current URL
                # with the menu URL but if the menu is linked to a page we don't
                # consider it active if the paths don't match exactly.
                if self.page_id and menu_url.path != request_url.path:
                    return False
                if not (
                    set(menu_url.decode_query().items(multi=True))
                    <= set(request_url.decode_query().items(multi=True))
                ):
                    # correct path but query arguments does not match
                    return False
                if menu_url.netloc and menu_url.netloc != request_url.netloc:
                    # correct path but not correct domain
                    return False
                return True
        else:
            # Child match (dropdown menu), `self` is just a parent/container,
            # don't check its URL, consider only its children
            if any(child._is_active() for child in self.child_id):
                return True

        return False
