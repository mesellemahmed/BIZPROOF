def _reference_exchange_rate(ref_doc, args: dict) -> float:
	"""Exchange rate of the party account on the reference document's posting date."""
	if not args.get("party_account"):
		return 1

	from erpnext.accounts.doctype.journal_entry.journal_entry import get_exchange_rate

	return get_exchange_rate(
		ref_doc.get("posting_date") or ref_doc.get("transaction_date"),
		args.get("party_account"),
		args.get("party_account_currency"),
		ref_doc.company,
		ref_doc.doctype,
		ref_doc.name,
	)
