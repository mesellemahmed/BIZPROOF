def _get_menu_class_for_instance(menu_class, instance):
    """
    Returns a new menu class that subclasses
    menu_class but is bound to instance.
    This means it sets the "instance" attribute of the class.
    """
    attrs = {'instance': instance}
    class_name = menu_class.__name__
    meta_class = type(menu_class)
    return meta_class(class_name, (menu_class,), attrs)
