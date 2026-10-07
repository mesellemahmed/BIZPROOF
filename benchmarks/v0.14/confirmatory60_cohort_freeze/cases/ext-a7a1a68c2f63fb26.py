def test_subnet_update_post_invalid_routes_three_entries(self):
    host_routes = 'aaaa,bbbb,cccc'
    res = self._test_subnet_update_post_invalid(host_routes)
    self.assertContains(res,
                        'Host Routes format error: '
                        'Destination CIDR and Next Hop must be specified '
                        '(value=%s)' % host_routes)
