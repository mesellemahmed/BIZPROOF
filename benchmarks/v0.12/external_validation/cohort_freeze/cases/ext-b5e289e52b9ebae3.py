    def get_for_object(self, obj, aggregate_data=False):
        """
        Return all applicable ConfigContexts for a given object. Only active ConfigContexts will be included.

        WARNING: This method's scope-matching logic is mirrored (inverted) by ConfigContext.get_affected_objects(),
        which powers cache invalidation. Any change to the matching criteria here MUST be applied there as well, or
        pre-rendered config context caches will go stale. See extras/models/configs.py.

        Args:
          aggregate_data: If True, use the JSONBAgg aggregate function to return only the list of JSON data objects
        """

        # Device type and location assignment are relevant only for Devices
        device_type = getattr(obj, 'device_type', None)
        location = getattr(obj, 'location', None)
        locations = location.get_ancestors(include_self=True) if location else []

        # Get assigned cluster, group, and type (if any)
        cluster = getattr(obj, 'cluster', None)
        cluster_type = getattr(cluster, 'type', None)
        cluster_group = getattr(cluster, 'group', None)

        # Get the group of the assigned tenant, if any
        tenant_group = obj.tenant.group if obj.tenant else None

        # Match against the directly assigned region as well as any parent regions.
        region = getattr(obj.site, 'region', None)
        regions = region.get_ancestors(include_self=True) if region else []

        # Match against the directly assigned site group as well as any parent site groups.
        sitegroup = getattr(obj.site, 'group', None)
        sitegroups = sitegroup.get_ancestors(include_self=True) if sitegroup else []

        # Match against the directly assigned role as well as any parent roles.
        device_roles = obj.role.get_ancestors(include_self=True) if obj.role else []

        # Match against the directly assigned platform as well as any parent platforms.
        platform = getattr(obj, 'platform', None)
        platforms = platform.get_ancestors(include_self=True) if platform else []

        queryset = self.filter(
            Q(regions__in=regions) | Q(regions=None),
            Q(site_groups__in=sitegroups) | Q(site_groups=None),
            Q(sites=obj.site) | Q(sites=None),
            Q(locations__in=locations) | Q(locations=None),
            Q(device_types=device_type) | Q(device_types=None),
            Q(roles__in=device_roles) | Q(roles=None),
            Q(platforms__in=platforms) | Q(platforms=None),
            Q(cluster_types=cluster_type) | Q(cluster_types=None),
            Q(cluster_groups=cluster_group) | Q(cluster_groups=None),
            Q(clusters=cluster) | Q(clusters=None),
            Q(tenant_groups=tenant_group) | Q(tenant_groups=None),
            Q(tenants=obj.tenant) | Q(tenants=None),
            Q(tags__slug__in=obj.tags.slugs()) | Q(tags=None),
            is_active=True,
        ).order_by('weight', 'name').distinct()

        if aggregate_data:
            return queryset.aggregate(
                config_context_data=JSONBAgg('data', order_by=['weight', 'name'])
            )['config_context_data']

        return queryset
