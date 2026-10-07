def json_validator(value: Any) -> Any:
    '''Validate and parse a JSON value.

    dicts and lists will be returned untouched, while other values
    will be run through a JSON parser before being returned. If the
    parsing fails, raise an Invalid exception.
    '''
    if isinstance(value, (list, dict)):
        return value
    try:
        value = json.loads(value)
    except (ValueError, TypeError):
        raise df.Invalid('Cannot parse JSON')
    return value
