    def edit_plugin(self, request, plugin_id):
        try:
            plugin_id = int(plugin_id)
        except ValueError:
            return HttpResponseNotFound(_("Plugin not found"))

        obj = self._get_plugin_from_id(plugin_id)

        # CMSPluginBase subclass instance
        plugin_instance = obj.get_plugin_class_instance(admin=self.admin_site)

        if not self.has_change_plugin_permission(request, obj):
            return HttpResponseForbidden(_("You do not have permission to edit this plugin"))

        if not obj.placeholder.check_source(request.user):
            message = _("You do not have permission to edit this plugin")
            return HttpResponseForbidden(message)

        response = plugin_instance.change_view(request, str(plugin_id))

        plugin = getattr(plugin_instance, 'saved_object', None)

        if plugin:
            plugin.placeholder.clear_cache(plugin.language)

        if plugin_instance._operation_token:
            self._send_post_placeholder_operation(
                request,
                operation=operations.CHANGE_PLUGIN,
                token=plugin_instance._operation_token,
                old_plugin=obj,
                new_plugin=plugin,
                placeholder=plugin.placeholder,
            )
        return response
