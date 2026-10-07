    def _expected(self, filter_string):
        my_tenant_id = self.request.user.tenant_id
        images = self.images.list()
        special = map(lambda t: t['tenant'], self.filter_tenants)

        if filter_string == 'public':
            return [im for im in images if im.is_public]
        if filter_string == 'shared':
            return [im for im in images
                    if (not im.is_public and
                        im.owner != my_tenant_id and
                        im.owner not in special)]
        if filter_string == 'project':
            filter_string = my_tenant_id
        return [im for im in images if im.owner == filter_string]
