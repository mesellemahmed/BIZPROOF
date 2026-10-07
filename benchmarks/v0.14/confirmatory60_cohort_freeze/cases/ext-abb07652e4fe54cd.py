def get_initial(self):
    results = super().get_initial()
    results['dns_nameservers'] = self.get_default_dns_servers()
    return results
