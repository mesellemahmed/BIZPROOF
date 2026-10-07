def get_purchase_invoice_fields(self, doctype):
	return [
		doctype.grand_total,
		doctype.base_total,
		doctype.bill_no.as_("supplier_invoice_no"),
		doctype.bill_date.as_("supplier_invoice_date"),
	]
