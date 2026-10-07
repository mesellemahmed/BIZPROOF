    def _get_journals_payment_method_information(self):
        method_information = self.env['account.payment.method']._get_payment_method_information()
        unique_electronic_ids = set()
        electronic_names = set()
        pay_methods = self.env['account.payment.method'].sudo().search([('code', 'in', list(method_information.keys()))])
        manage_providers = 'payment_provider_id' in self.env['account.payment.method.line']._fields

        # Split the payment method information per id.
        method_information_mapping = {}
        for pay_method in pay_methods:
            code = pay_method.code
            values = method_information_mapping[pay_method.id] = {
                **method_information[code],
                'payment_method': pay_method,
                'company_journals': {},
            }
            if values['mode'] == 'unique':
                unique_electronic_ids.add(pay_method.id)
            elif manage_providers and values['mode'] == 'electronic':
                unique_electronic_ids.add(pay_method.id)
                electronic_names.add(pay_method.code)

        # Load the provider to manage 'electronic' payment methods.
        providers_per_code = {}
        if manage_providers:
            providers = self.env['payment.provider'].sudo().search([
                *self.env['payment.provider']._check_company_domain(self.company_id),
                ('code', 'in', tuple(electronic_names)),
            ])
            for provider in providers:
                providers_per_code.setdefault(provider.company_id.id, {}).setdefault(provider._get_code(), set()).add(provider.id)

        # Collect the existing unique/electronic payment method lines.
        if unique_electronic_ids:
            fnames = ['payment_method_id', 'journal_id']
            if manage_providers:
                fnames.append('payment_provider_id')
            self.env['account.payment.method.line'].flush_model(fnames=fnames)

            self.env.cr.execute(
                f'''
                    SELECT
                        apm.id,
                        journal.company_id,
                        journal.id,
                        {'apml.payment_provider_id' if manage_providers else 'NULL'}
                    FROM account_payment_method_line apml
                    JOIN account_journal journal ON journal.id = apml.journal_id
                    JOIN account_payment_method apm ON apm.id = apml.payment_method_id
                    WHERE apm.id IN %s
                ''',
                [tuple(unique_electronic_ids)],
            )
            for pay_method_id, company_id, journal_id, provider_id in self.env.cr.fetchall():
                values = method_information_mapping[pay_method_id]
                is_electronic = manage_providers and values['mode'] == 'electronic'
                if is_electronic:
                    journal_ids = values['company_journals'].setdefault(company_id, {}).setdefault(provider_id, [])
                else:
                    journal_ids = values['company_journals'].setdefault(company_id, [])
                journal_ids.append(journal_id)
        return {
            'pay_methods': pay_methods,
            'manage_providers': manage_providers,
            'method_information_mapping': method_information_mapping,
            'providers_per_code': providers_per_code,
        }
