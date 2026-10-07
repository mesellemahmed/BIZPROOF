def update_merge_list(data_list: list[Any],
                      update_list: Union[list[Any], Any],
                      parent_path: FlattenKey = ()) -> None:
    """
    update data_list entries in-place based on update_list.

    raise DataError on incompatible types such as replacing a dict with a list
    """
    if not isinstance(update_list, list):
        raise DataError('Expected list for %s' % '__'.join(
            str(p) for p in parent_path))

    for i, v in enumerate(update_list):
        if i >= len(data_list):
            data_list.append(v)
        elif isinstance(data_list[i], dict):
            update_merge_dict(data_list[i], v, parent_path + (i,))
        elif isinstance(data_list[i], list):
            update_merge_list(data_list[i], v, parent_path + (i,))
        else:
            data_list[i] = v
