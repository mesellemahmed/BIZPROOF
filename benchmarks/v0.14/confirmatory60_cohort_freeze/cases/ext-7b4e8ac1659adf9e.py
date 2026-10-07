    def get(self, request):
        """Get a list of server groups.

        The listing result is an object with property "items".
        """
        result = api.nova.server_group_list(request)
        return {'items': [u.to_dict() for u in result]}
