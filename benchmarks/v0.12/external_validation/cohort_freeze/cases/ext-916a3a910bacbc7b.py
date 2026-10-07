    def get_paginated_response(self, data):
        response_data = [
            ("count", self.page.paginator.count),
            ("next", self.get_next_link()),
            ("previous", self.get_previous_link()),
        ]
        if self._should_include_all():
            response_data.append(("all", self.get_all_result_ids()))
        response_data.append(("results", data))

        return Response(
            OrderedDict(response_data),
        )
