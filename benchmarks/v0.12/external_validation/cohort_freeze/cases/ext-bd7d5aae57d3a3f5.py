def execute(filters=None):
	columns, data = [], []
	if not filters.get("periodicity"):
		filters["periodicity"] = "Daily"

	columns = get_columns()
	data, timeslot_wise_count = get_data(filters)
	chart = get_chart_data(timeslot_wise_count)
	return columns, data, None, chart
