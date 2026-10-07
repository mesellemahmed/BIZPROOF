    def update_notification(self, cron_mode=True):
        """
        Send a message to Odoo's publisher warranty server to check the
        validity of the contracts, get notifications, etc...

        @param cron_mode: If true, catch all exceptions (appropriate for usage in a cron).
        @type cron_mode: boolean
        """
        try:
            try:
                result = self._get_sys_logs()
            except Exception:
                if cron_mode:   # we don't want to see any stack trace in cron
                    return False
                _logger.debug("Exception while sending a get logs messages", exc_info=1)
                raise UserError(_("Error during communication with the publisher warranty server."))
            # old behavior based on res.log; now on mail.message, that is not necessarily installed
            user = self.env['res.users'].sudo().browse(SUPERUSER_ID)
            if poster := self.sudo().env.ref('mail.channel_all_employees', raise_if_not_found=False):
                for message in result["messages"]:
                    with contextlib.suppress(Exception):
                        poster.message_post(body=message, subtype_xmlid='mail.mt_comment', partner_ids=[user.partner_id.id])
            if result.get('enterprise_info'):
                # Update expiration date
                set_str = self.env['ir.config_parameter'].sudo().set_str
                set_str('database.expiration_date', result['enterprise_info'].get('expiration_date'))
                set_str('database.expiration_reason', result['enterprise_info'].get('expiration_reason', 'trial'))
                set_str('database.enterprise_code', result['enterprise_info'].get('enterprise_code'))
                set_str('database.already_linked_subscription_url', result['enterprise_info'].get('database_already_linked_subscription_url'))
                set_str('database.already_linked_email', result['enterprise_info'].get('database_already_linked_email'))
                set_str('database.already_linked_send_mail_url', result['enterprise_info'].get('database_already_linked_send_mail_url'))

        except Exception:
            if cron_mode:
                return False    # we don't want to see any stack trace in cron
            else:
                raise
        return True
