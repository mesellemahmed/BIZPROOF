def validate_input(cls, info: ResolveInfo, data):
    obj = cls.get_node_or_error(info, data["id"])
    if not isinstance(obj, Order | Checkout):
        code = error_codes.TaxExemptionManageErrorCode.NOT_FOUND.value
        message = "Invalid object ID. Only Checkout and Order ID's are accepted."
        raise ValidationError({"id": ValidationError(code=code, message=message)})
