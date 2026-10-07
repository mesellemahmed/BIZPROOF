def execute(filters=None):
	validate_filters(filters)
	dimension_list = get_dimensions(filters)

	if not dimension_list:
		return [], []

	columns = get_columns(dimension_list)
	data = get_data(filters, dimension_list)

	return columns, data
