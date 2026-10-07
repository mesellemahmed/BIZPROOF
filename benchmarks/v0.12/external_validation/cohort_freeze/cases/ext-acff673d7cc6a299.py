def _normalize_type(_type: Any) -> str:
    if isinstance(_type, domain_object.DomainObject):
        _type = _type.__class__
    if isinstance(_type, type):
        _type = _type.__name__
    return _type.strip().lower()
