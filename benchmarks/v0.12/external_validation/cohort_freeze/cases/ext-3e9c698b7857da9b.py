def add_url_param(alternative_url: Optional[str] = None,
                  controller: Optional[str] = None,
                  action: Optional[str] = None,
                  extras: Optional[dict[str, Any]] = None,
                  new_params: Optional[dict[str, Any]] = None) -> str:
    '''
    Adds extra parameters to existing ones

    controller action & extras (dict) are used to create the base url via
    :py:func:`~ckan.lib.helpers.url_for` controller & action default to the
    current ones

    This can be overridden providing an alternative_url, which will be used
    instead.
    '''

    params_items = request.args.items(multi=True)
    params_nopage = [
        (k, v) for k, v in params_items
        if k != 'page'
    ]
    if new_params:
        params_nopage += list(new_params.items())
    if alternative_url:
        return _url_with_params(alternative_url, params_nopage)
    return _create_url_with_params(params=params_nopage, controller=controller,
                                   action=action, extras=extras)
