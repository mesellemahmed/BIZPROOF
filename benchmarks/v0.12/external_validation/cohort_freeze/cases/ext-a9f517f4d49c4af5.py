def should_render(self, context):
    obj = get_obj_from_context(context)
    return obj.group_type != DynamicGroupTypeChoices.TYPE_STATIC
