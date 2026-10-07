def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        rrule=dict(),
        name=dict(required=True),
        new_name=dict(),
        description=dict(),
        execution_environment=dict(type='str'),
        extra_data=dict(type='dict'),
        forks=dict(type='int'),
        instance_groups=dict(type='list', elements='str'),
        inventory=dict(),
        job_slice_count=dict(type='int'),
        labels=dict(type='list', elements='str'),
        timeout=dict(type='int'),
        credentials=dict(type='list', elements='str'),
        scm_branch=dict(),
        job_type=dict(choices=['run', 'check']),
        job_tags=dict(),
        skip_tags=dict(),
        limit=dict(),
        diff_mode=dict(type='bool'),
        verbosity=dict(type='int', choices=[0, 1, 2, 3, 4, 5]),
        unified_job_template=dict(),
        organization=dict(),
        enabled=dict(type='bool'),
        state=dict(choices=['present', 'absent', 'exists'], default='present'),
    )

    # Create a module for ourselves
    module = ControllerAPIModule(argument_spec=argument_spec)

    # Extract our parameters
    rrule = module.params.get('rrule')
    name = module.params.get('name')
    new_name = module.params.get("new_name")
    description = module.params.get('description')
    execution_environment = module.params.get('execution_environment')
    extra_data = module.params.get('extra_data')
    forks = module.params.get('forks')
    instance_groups = module.params.get('instance_groups')
    inventory = module.params.get('inventory')
    job_slice_count = module.params.get('job_slice_count')
    labels = module.params.get('labels')
    timeout = module.params.get('timeout')
    credentials = module.params.get('credentials')
    scm_branch = module.params.get('scm_branch')
    job_type = module.params.get('job_type')
    job_tags = module.params.get('job_tags')
    skip_tags = module.params.get('skip_tags')
    limit = module.params.get('limit')
    diff_mode = module.params.get('diff_mode')
    verbosity = module.params.get('verbosity')
    unified_job_template = module.params.get('unified_job_template')
    organization = module.params.get('organization')
    enabled = module.params.get('enabled')
    state = module.params.get('state')

    # Attempt to look up the related items the user specified (these will fail the module if not found)
    inventory_id = None
    if inventory:
        inventory_id = module.resolve_name_to_id('inventories', inventory)
    search_fields = {}
    sched_search_fields = {}
    if organization:
        search_fields['organization'] = module.resolve_name_to_id('organizations', organization)
    unified_job_template_id = None
    if unified_job_template:
        search_fields['name'] = unified_job_template
        unified_job_template_id = module.get_one('unified_job_templates', **{'data': search_fields})['id']
        sched_search_fields['unified_job_template'] = unified_job_template_id

    # Attempt to look up an existing item based on the provided data
    existing_item = module.get_one('schedules', name_or_id=name, check_exists=(state == 'exists'), **{'data': sched_search_fields})

    if state == 'absent':
        # If the state was absent we can let the module delete it if needed, the module will handle exiting from this
        module.delete_if_needed(existing_item)

    # We need to clear out the name from the search fields so we can use name_or_id in the following searches
    if 'name' in search_fields:
        del search_fields['name']

    # Create the data that gets sent for create and update
    new_fields = {}
    if execution_environment is not None:
        if execution_environment == '':
            new_fields['execution_environment'] = ''
        else:
            ee = module.get_one('execution_environments', name_or_id=execution_environment, **{'data': search_fields})
            if ee is None:
                ee2 = module.get_one('execution_environments', name_or_id=execution_environment)
                if ee2 is None or ee2['organization'] is not None:
                    module.fail_json(msg='could not find execution_environment entry with name {0}'.format(execution_environment))
                else:
                    new_fields['execution_environment'] = ee2['id']
            else:
                new_fields['execution_environment'] = ee['id']

    association_fields = {}

    if credentials is not None:
        association_fields['credentials'] = []
        for item in credentials:
            association_fields['credentials'].append(module.resolve_name_to_id('credentials', item))

    # We need to clear out the organization from the search fields the searches for labels and instance_groups doesnt support it and won't be needed anymore
    if 'organization' in search_fields:
        del search_fields['organization']

    if labels is not None:
        association_fields['labels'] = []
        for item in labels:
            label_id = module.get_one('labels', name_or_id=item, **{'data': search_fields})
            if label_id is None:
                module.fail_json(msg='Could not find label entry with name {0}'.format(item))
            else:
                association_fields['labels'].append(label_id['id'])

    if instance_groups is not None:
        association_fields['instance_groups'] = []
        for item in instance_groups:
            instance_group_id = module.get_one('instance_groups', name_or_id=item, **{'data': search_fields})
            if instance_group_id is None:
                module.fail_json(msg='Could not find instance_group entry with name {0}'.format(item))
            else:
                association_fields['instance_groups'].append(instance_group_id['id'])

    if rrule is not None:
        new_fields['rrule'] = rrule
    new_fields['name'] = new_name if new_name else (module.get_item_name(existing_item) if existing_item else name)
    if description is not None:
        new_fields['description'] = description
    if extra_data is not None:
        new_fields['extra_data'] = extra_data
    if inventory is not None:
        new_fields['inventory'] = inventory_id
    if scm_branch is not None:
        new_fields['scm_branch'] = scm_branch
    if job_type is not None:
        new_fields['job_type'] = job_type
    if job_tags is not None:
        new_fields['job_tags'] = job_tags
    if skip_tags is not None:
        new_fields['skip_tags'] = skip_tags
    if limit is not None:
        new_fields['limit'] = limit
    if diff_mode is not None:
        new_fields['diff_mode'] = diff_mode
    if verbosity is not None:
        new_fields['verbosity'] = verbosity
    if unified_job_template is not None:
        new_fields['unified_job_template'] = unified_job_template_id
    if enabled is not None:
        new_fields['enabled'] = enabled
    if forks is not None:
        new_fields['forks'] = forks
    if job_slice_count is not None:
        new_fields['job_slice_count'] = job_slice_count
    if timeout is not None:
        new_fields['timeout'] = timeout

    # If the state was present and we can let the module build or update the existing item, this will return on its own
    module.create_or_update_if_needed(
        existing_item,
        new_fields,
        endpoint='schedules',
        item_type='schedule',
        associations=association_fields,
    )
