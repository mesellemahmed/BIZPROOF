def get_context_data(self, **kwargs):
    result = super().get_context_data(**kwargs)
    if self.request.user.has_perm("person.delete_speakerprofile", self.object):
        result["submit_buttons_extra"] = [delete_link(self.object.orga_urls.delete)]
    return result
