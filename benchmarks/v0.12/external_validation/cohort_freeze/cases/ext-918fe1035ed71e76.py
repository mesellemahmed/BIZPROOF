def getChild(self, path: str, request: Request) -> resource.Resource:
    # The child of a catch-all unrecognised request handler
    # is itself another unrecognised request handler.
    # We can return any UnrecognizedRequestResource that doesn't
    # have children.
    assert len(_BLANK_LEAF_UNRECOGNISED_REQUEST_RESOURCE.children) == 0
    return _BLANK_LEAF_UNRECOGNISED_REQUEST_RESOURCE
