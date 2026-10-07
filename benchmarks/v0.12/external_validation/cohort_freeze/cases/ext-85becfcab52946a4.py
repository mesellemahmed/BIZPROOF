def _mysql_varbin_to_network(alias=None):
    if alias:
        return f"HEX({alias}.network)"
    return "HEX(network)"
