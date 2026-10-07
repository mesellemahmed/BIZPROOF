def create_consumer(self, consumer_ref, initiator=None):
    consumer_ref = consumer_ref.copy()
    consumer_ref['secret'] = uuid.uuid4().hex
    ret = self.driver.create_consumer(consumer_ref)
    notifications.Audit.created(self._CONSUMER, ret['id'], initiator)
    return ret
