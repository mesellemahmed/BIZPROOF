def _authenticate_with_basic_auth(self):
    if self.username and self.password:
        # use api url /api/v2/me to get current user info as a testing request
        me_url = self.build_url("me").geturl()
        self.session.open(
            "GET",
            me_url,
            validate_certs=self.verify_ssl,
            timeout=self.request_timeout,
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "Authorization": self._get_basic_authorization_header(),
            },
        )
