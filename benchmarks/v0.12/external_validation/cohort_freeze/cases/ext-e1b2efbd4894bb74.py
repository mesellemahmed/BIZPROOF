	def validate_outstanding_sdbnb_transactions(self, account):
		GLEntry = frappe.qb.DocType("GL Entry")
		DeliveryNote = frappe.qb.DocType("Delivery Note")

		delivery_notes = (
			frappe.qb.from_(GLEntry)
			.join(DeliveryNote)
			.on((GLEntry.voucher_type == "Delivery Note") & (GLEntry.voucher_no == DeliveryNote.name))
			.select(DeliveryNote.name)
			.where(
				(GLEntry.is_cancelled == 0)
				& (GLEntry.company == self.name)
				& (GLEntry.account == account)
				& (DeliveryNote.per_billed < 100)
				& (DeliveryNote.docstatus == 1)
				& (DeliveryNote.status.isin(["To Bill", "Partially Billed"]))
			)
			.distinct()
			.run(pluck=True)
		)

		if delivery_notes:
			dn_links = ", ".join(get_link_to_form("Delivery Note", dn) for dn in delivery_notes[:10])

			frappe.throw(
				_(
					"Stock Delivered But Not Billed Account cannot be changed or disabled since account {0} contains outstanding Delivery Notes: {1}"
				).format(
					bold(account),
					dn_links,
				)
			)
