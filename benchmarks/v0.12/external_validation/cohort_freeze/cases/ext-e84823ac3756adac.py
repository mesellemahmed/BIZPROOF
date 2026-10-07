def allocate_open_payment_requests_to_references(references=None, precision=None):
	"""
	Allocate unpaid Payment Requests to the references. \n
	---
	- Allocation based on below factors
	    - Reference Allocated Amount
	    - Reference Outstanding Amount (With Payment Terms or without Payment Terms)
	    - Reference Payment Request's outstanding amount
	---
	- Allocation based on below scenarios
	    - Reference's Allocated Amount == Payment Request's Outstanding Amount
	        - Allocate the Payment Request to the reference
	        - This PR will not be allocated further
	    - Reference's Allocated Amount < Payment Request's Outstanding Amount
	        - Allocate the Payment Request to the reference
	        - Reduce the PR's outstanding amount by the allocated amount
	        - This PR can be allocated further
	    - Reference's Allocated Amount > Payment Request's Outstanding Amount
	        - Allocate the Payment Request to the reference
	        - Reduce Allocated Amount of the reference by the PR's outstanding amount
	        - Create a new row for the remaining amount until the Allocated Amount is 0
	            - Allocate PR if available
	---
	- Note:
	    - Priority is given to the first Payment Request of respective references.
	    - Single Reference can have multiple rows.
	        - With Payment Terms or without Payment Terms
	        - With Payment Request or without Payment Request
	"""
	if not references:
		return

	# get all unpaid payment requests for the references
	references_open_payment_requests = get_open_payment_requests_for_references(references)

	if not references_open_payment_requests:
		return

	if not precision:
		precision = references[0].precision("allocated_amount")

	# to manage new rows
	row_number = 1
	MOVE_TO_NEXT_ROW = 1
	TO_SKIP_NEW_ROW = 2

	while row_number <= len(references):
		row = references[row_number - 1]
		reference_key = (row.reference_doctype, row.reference_name)

		# update the idx to maintain the order
		row.idx = row_number

		# unpaid payment requests for the reference
		reference_payment_requests = references_open_payment_requests.get(reference_key)

		if not reference_payment_requests:
			row_number += MOVE_TO_NEXT_ROW  # to move to next reference row
			continue

		# get the first payment request and its outstanding amount
		payment_request, pr_outstanding_amount = next(iter(reference_payment_requests.items()))
		allocated_amount = row.allocated_amount

		# allocate the payment request to the reference and PR's outstanding amount
		row.payment_request = payment_request

		if pr_outstanding_amount == allocated_amount:
			del reference_payment_requests[payment_request]
			row_number += MOVE_TO_NEXT_ROW

		elif pr_outstanding_amount > allocated_amount:
			# reduce the outstanding amount of the payment request
			reference_payment_requests[payment_request] -= allocated_amount
			row_number += MOVE_TO_NEXT_ROW

		else:
			# split the reference row to allocate the remaining amount
			del reference_payment_requests[payment_request]
			row.allocated_amount = pr_outstanding_amount
			allocated_amount = flt(allocated_amount - pr_outstanding_amount, precision)

			# set the remaining amount to the next row
			while allocated_amount:
				# create a new row for the remaining amount
				new_row = frappe.copy_doc(row)
				references.insert(row_number, new_row)

				# get the first payment request and its outstanding amount
				payment_request, pr_outstanding_amount = next(
					iter(reference_payment_requests.items()), (None, None)
				)

				# update new row
				new_row.idx = row_number + 1
				new_row.payment_request = payment_request
				new_row.allocated_amount = min(
					pr_outstanding_amount if pr_outstanding_amount else allocated_amount, allocated_amount
				)

				if not payment_request or not pr_outstanding_amount:
					row_number += TO_SKIP_NEW_ROW
					break

				elif pr_outstanding_amount == allocated_amount:
					del reference_payment_requests[payment_request]
					row_number += TO_SKIP_NEW_ROW
					break

				elif pr_outstanding_amount > allocated_amount:
					reference_payment_requests[payment_request] -= allocated_amount
					row_number += TO_SKIP_NEW_ROW
					break

				else:
					allocated_amount = flt(allocated_amount - pr_outstanding_amount, precision)
					del reference_payment_requests[payment_request]
					row_number += MOVE_TO_NEXT_ROW
