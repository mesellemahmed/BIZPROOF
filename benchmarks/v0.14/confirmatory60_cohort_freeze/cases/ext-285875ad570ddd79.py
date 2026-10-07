    def _test_servers_paginate_do(self,
                                  marker,
                                  servers,
                                  has_more,
                                  has_prev):
        flavors = self.flavors.list()
        tenants = self.tenants.list()
        # UUID indices are unique and are guaranteed being deterministic.
        for i, server in enumerate(servers):
            server.flavor['id'] = str(uuid.UUID(int=i))

        self.mock_server_list_paged.return_value = [
            servers, has_more, has_prev]
        self.mock_flavor_list.return_value = flavors
        self.mock_image_list_detailed.side_effect =\
            self._mock_image_list_detailed_side_effect
        self.mock_volume_list.return_value = self.cinder_volumes.list()
        self.mock_tenant_list.return_value = [tenants, False]
        self.mock_flavor_get.side_effect = self.exceptions.nova

        if marker:
            url = "?".join([INDEX_URL, "marker={}".format(marker)])
        else:
            url = INDEX_URL
        res = self.client.get(url)
        self.assertTemplateUsed(res, INDEX_TEMPLATE)
        self.assertEqual(res.status_code, 200)

        self.mock_tenant_list.assert_called_once_with(test.IsHttpRequest())
        self.assertEqual(self.mock_image_list_detailed.call_count, 4)
        self.mock_flavor_list.assert_called_once_with(test.IsHttpRequest())
        search_opts = {'marker': marker, 'paginate': True, 'all_tenants': True}
        self.mock_server_list_paged.assert_called_once_with(
            test.IsHttpRequest(),
            sort_dir='desc',
            search_opts=search_opts)
        self.mock_flavor_get.assert_has_calls(
            [mock.call(test.IsHttpRequest(), s.flavor['id']) for s in servers])
        self.assertEqual(len(servers), self.mock_flavor_get.call_count)

        return res
