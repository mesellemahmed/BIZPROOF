    def get_all_entity_ids(self, max_results: int = 1000) -> list[str]:
        """
        Return a list of the IDs of all indexed packages.
        """
        query = "*:*"
        fq = "+site_id:\"%s\" " % config.get('ckan.site_id')
        fq += "+state:active "

        conn = make_connection()
        data = conn.search(query, fq=fq, rows=max_results, fl='id')
        return [r.get('id') for r in data.docs]
