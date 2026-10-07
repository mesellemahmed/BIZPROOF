def get_issued_items_cost():
	se = frappe.qb.DocType("Stock Entry")
	se_item = frappe.qb.DocType("Stock Entry Detail")
	se_items = (
		frappe.qb.from_(se)
		.inner_join(se_item)
		.on(se.name == se_item.parent)
		.select(se.project, Sum(se_item.amount).as_("amount"))
		.where(
			(se.docstatus == 1)
			& (se_item.t_warehouse.isnull() | (se_item.t_warehouse == ""))
			& (se.project != "")
		)
		.groupby(se.project)
		.run(as_dict=1)
	)

	se_item_map = {}
	for item in se_items:
		se_item_map.setdefault(item.project, item.amount)

	return se_item_map
