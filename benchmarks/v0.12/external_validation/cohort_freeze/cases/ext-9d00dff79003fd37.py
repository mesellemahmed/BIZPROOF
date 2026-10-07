def get_extra_context(self, request, instance):
    return {
        'related_models': self.get_related_models(
            request,
            instance,
            omit=(CircuitTermination,),
            extra=(
                (
                    Circuit.objects.restrict(request.user, 'view').filter(terminations___provider_network=instance),
                    'provider_network_id',
                ),
                (
                    CircuitTermination.objects.restrict(request.user, 'view').filter(_provider_network=instance),
                    'provider_network_id',
                ),
            ),
        ),
    }
