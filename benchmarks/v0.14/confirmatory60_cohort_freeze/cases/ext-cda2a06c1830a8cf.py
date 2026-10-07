def delete_handler(self, request, *args, **kwargs):
    if not can_delete_submission_type(self.object):
        messages.error(
            request,
            _("This session type is in use in a proposal and cannot be deleted."),
        )
        return self.delete_view(request, *args, **kwargs)
    try:
        return super().delete_handler(request, *args, **kwargs)
    except ProtectedError:  # pragma: no cover -- race fallback
        messages.error(
            request,
            _("This session type is in use in a proposal and cannot be deleted."),
        )
        return self.delete_view(request, *args, **kwargs)
