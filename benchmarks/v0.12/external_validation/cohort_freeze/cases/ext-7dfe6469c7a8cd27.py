def _material_request_mapping(postprocess, allocation):
	return {
		"Work Order": {
			"doctype": "Material Request",
			"validation": {"docstatus": ["=", 1]},
			"field_map": {"name": "work_order"},
		},
		"Work Order Item": {
			"doctype": "Material Request Item",
			"field_map": [
				("stock_uom", "uom"),
				("source_warehouse", "from_warehouse"),
			],
			"postprocess": postprocess,
			"condition": lambda doc: _allocation_key(doc) in allocation,
		},
	}
