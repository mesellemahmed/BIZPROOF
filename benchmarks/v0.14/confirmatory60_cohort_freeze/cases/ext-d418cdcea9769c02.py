def get_form_context(self, value, prefix="", errors=None):
    dict_value = {
        "image": value,
        "alt_text": value and value.contextual_alt_text,
        "decorative": value and value.decorative,
    }
    context = super().get_form_context(dict_value, prefix=prefix, errors=errors)
    context["suggested_alt_text"] = value
    return context
