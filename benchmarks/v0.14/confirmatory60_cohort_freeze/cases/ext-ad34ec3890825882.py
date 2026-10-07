    def start(self, stop=False):
        self.logger.debug("setting signal handlers")
        set_limit_memory_hard()
        if os.name == 'posix':
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            signal.signal(signal.SIGCHLD, self.signal_handler)
            signal.signal(signal.SIGHUP, self.signal_handler)
            signal.signal(signal.SIGXCPU, self.signal_handler)
            signal.signal(signal.SIGQUIT, dumpstacks)
            signal.signal(signal.SIGUSR1, log_ormcache_stats)
            signal.signal(signal.SIGUSR2, log_ormcache_stats)
        elif os.name == 'nt':
            import win32api  # noqa: PLC0415
            win32api.SetConsoleCtrlHandler(lambda sig: self.signal_handler(sig, None), 1)

        if config['test_enable'] or (config['http_enable'] and not stop):
            # some tests need the http daemon to be available...
            self.http_spawn()
