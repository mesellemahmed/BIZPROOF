    def __init__(self, hs: "HomeServer"):
        super().__init__(hs)

        self.registeration_handler = hs.get_registration_handler()
        self.store = hs.get_datastores().main
        self.clock = hs.get_clock()
        self.distributor = hs.get_distributor()
