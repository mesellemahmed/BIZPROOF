def validate_advance_entries(doc) -> None:
	"""Warn if a payment entry linked to the same order is not pulled as advance."""
	order_field = "sales_order" if doc.doctype == "Sales Invoice" else "purchase_order"
	order_list = list(set(d.get(order_field) for d in doc.get("items") if d.get(order_field)))

	if not order_list:
		return

	advance_entries = get_advance_entries(doc, include_unallocated=False)

	if advance_entries:
		advance_entries_against_si = [d.reference_name for d in doc.get("advances")]
		for d in advance_entries:
			if not advance_entries_against_si or d.reference_name not in advance_entries_against_si:
				frappe.msgprint(
					_(
						"Payment Entry {0} is linked against Order {1}, check if it should be pulled as advance in this invoice."
					).format(d.reference_name, d.against_order)
				)
