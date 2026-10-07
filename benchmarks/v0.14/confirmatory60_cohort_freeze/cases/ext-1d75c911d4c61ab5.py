def _get_volumes(self):
    # Gather our volumes to get their image metadata for instance
    try:
        volumes = api.cinder.volume_list(self.request)
        return dict((str(volume.id), volume) for volume in volumes)
    except Exception:
        exceptions.handle(self.request, ignore=True)
        return {}
