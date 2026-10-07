def get_toolbar_plugin_struct(plugins, slot=None, obj=None, page=None):
    """
    Return the list of plugins to render in the toolbar.
    The dictionary contains the label, the classname and the module for the
    plugin.
    Names and modules can be defined on a per-placeholder basis using
    'plugin_modules' and 'plugin_labels' attributes in CMS_PLACEHOLDER_CONF

    :param plugins: list of plugins
    :param slot: placeholder slot name
    :param page: the page
    :return: list of dictionaries
    """
    template = None

    obj = obj or page
    if page:
        import warnings

        warnings.warn(
            "The 'page' argument is deprecated. Please use 'obj' instead.",
            RemovedInDjangoCMS60Warning,
            stacklevel=2,
        )
    if obj and hasattr(obj, "get_template"):
        template = obj.get_template()

    modules = get_placeholder_conf("plugin_modules", slot, template, default={})
    names = get_placeholder_conf("plugin_labels", slot, template, default={})

    main_list = []

    # plugin.value points to the class name of the plugin
    # It's added on registration. TIL.
    for plugin in plugins:
        main_list.append(
            {
                "value": plugin.value,
                "name": names.get(plugin.value, plugin.name),
                "module": modules.get(plugin.value, plugin.module),
                "add_form": plugin.show_add_form and not plugin.is_slot,
            }
        )
    return sorted(main_list, key=operator.itemgetter("module"))
