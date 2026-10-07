    def get_conn(self, schema: str | None = None) -> Any:
        """Return a Hive connection object."""
        username: str | None = None
        password: str | None = None

        db = self.get_connection(self.get_conn_id())

        auth_mechanism = db.extra_dejson.get("auth_mechanism", "NONE")
        if auth_mechanism == "NONE" and db.login is None:
            # we need to give a username
            username = "airflow"
        kerberos_service_name = None
        if conf.get("core", "security") == "kerberos":
            auth_mechanism = db.extra_dejson.get("auth_mechanism", "KERBEROS")
            kerberos_service_name = db.extra_dejson.get("kerberos_service_name", "hive")

        # Pass through the password whenever the user has explicitly set one.
        # Previously this was restricted to LDAP/CUSTOM/PLAIN, which caused
        # user-provided passwords to be silently dropped for other auth modes
        # (pyhive defaults to sending "x" when password is None).
        if db.password:
            password = db.password

        from pyhive.hive import connect

        return connect(
            host=db.host,
            port=db.port,
            auth=auth_mechanism,
            kerberos_service_name=kerberos_service_name,
            username=db.login or username,
            password=password,
            database=schema or db.schema or "default",
        )
