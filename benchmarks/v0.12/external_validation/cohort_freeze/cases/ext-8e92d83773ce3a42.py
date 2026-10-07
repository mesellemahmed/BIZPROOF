	def update_status(self, status=None, update_modified=False):
		if not status:
			if self.docstatus == 0:
				status = "Draft"
			elif self.docstatus == 1:
				status = "Completed"

				if self.is_return:
					status = "Return"
				elif self.per_returned == 100:
					status = "Return Issued"

			elif self.docstatus == 2:
				status = "Cancelled"

			if self.is_return:
				frappe.get_doc("Subcontracting Receipt", self.return_against).update_status(
					update_modified=update_modified
				)

		if status:
			frappe.db.set_value(
				"Subcontracting Receipt", self.name, "status", status, update_modified=update_modified
			)
