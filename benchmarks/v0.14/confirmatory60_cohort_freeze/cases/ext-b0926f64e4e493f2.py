    def _send_peppol_documents(self, invoices_data_peppol, edi_user, params):
        try:
            response = edi_user._call_peppol_proxy(
                endpoint=edi_user._get_peppol_proxy_endpoint('1/send_document'),
                params=params,
            )
        except AccountEdiProxyError as e:
            for invoice, invoice_data in invoices_data_peppol.items():
                invoice.peppol_move_state = 'error'
                invoice_data['error'] = {'error_title': e.message}
        else:
            if error_vals := response.get('error'):
                # at the moment the only error that can happen here is ParticipantNotReady error
                for invoice, invoice_data in invoices_data_peppol.items():
                    invoice.peppol_move_state = 'error'
                    invoice_data['error'] = {
                        'error_title': get_peppol_error_message(self.env, error_vals),
                    }
            else:
                # the response only contains message uuids,
                # so we have to rely on the order to connect peppol messages to account.move
                attachments_linked_message = self._get_peppol_attachments_linked_message(edi_user)
                attachments_not_linked_message = _("Some attachments could not be sent with the XML:")
                for message, (invoice, invoice_data) in zip(response['messages'], invoices_data_peppol.items()):
                    invoice.peppol_message_uuid = message['message_uuid']
                    invoice.peppol_move_state = 'processing'
                    attachments_linked, attachments_not_linked = self._get_ubl_available_attachments(
                        invoice_data.get('mail_attachments_widget', []),
                        invoice_data['invoice_edi_format']
                    )
                    if attachments_not_linked:
                        invoice._message_log(body=attachments_not_linked_message, attachment_ids=attachments_not_linked.mapped('id'))

                    base_attachments = [
                        (invoice_data[key]['name'], invoice_data[key]['raw'])
                        for key in ['pdf_attachment_values', 'ubl_cii_xml_attachment_values']
                        if invoice_data.get(key)
                    ]

                    attachments_embedded = [
                        (attachment.name, attachment.raw)
                        for attachment in attachments_linked
                    ] + base_attachments

                    new_message = invoice.with_context(no_document=True).message_post(
                        body=attachments_linked_message,
                        attachments=attachments_embedded
                    )

                    if new_message.attachment_ids.ids:
                        if invoice.message_main_attachment_id in new_message.attachment_ids:
                            invoice.message_main_attachment_id = None
                        self.env.cr.execute("UPDATE ir_attachment SET res_id = NULL WHERE id IN %s", [tuple(new_message.attachment_ids.ids)])
                        new_message.attachment_ids.invalidate_recordset(['res_id', 'res_model'], flush=False)
                        new_message.attachment_ids.write({
                            'res_model': new_message._name,
                            'res_id': new_message.id,
                        })
                self.env.ref('account_peppol.ir_cron_peppol_get_message_status')._trigger(at=fields.Datetime.now() + timedelta(minutes=5))
