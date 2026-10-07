def get(self, request, *args, **kwargs):
    obj = self.get_object()
    data = dict(passwords_needed_to_start=obj.passwords_needed_to_start)
    return Response(data)
