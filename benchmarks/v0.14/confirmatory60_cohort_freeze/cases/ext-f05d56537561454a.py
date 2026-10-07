    def get_consumer(self, consumer_uuid, cert_pem, key_pem):
        """GET /consumers/{uuid} — retrieve consumer information from server.

        Best-effort: logs a warning on failure but never raises.

        Returns:
            Dict with consumer data (including 'idCert' with serial) on success,
            None on any failure.
        """
        url = f'{self.base_url}/consumers/{consumer_uuid}'
        try:
            with _temp_cert_files(cert_pem, key_pem) as (cert_path, key_path):
                resp = requests.get(
                    url,
                    cert=(cert_path, key_path),
                    verify=self.verify,
                    proxies=self.proxies,
                    timeout=30,
                )
            if resp.status_code == 200:
                logger.debug(f'Candlepin get_consumer successful for consumer {consumer_uuid}')
                return resp.json()
            logger.warning(f'Candlepin get_consumer returned unexpected status {resp.status_code} for consumer {consumer_uuid}')
            return None
        except Exception as e:
            logger.warning(f'Candlepin get_consumer failed for consumer {consumer_uuid}: {e}')
            return None
