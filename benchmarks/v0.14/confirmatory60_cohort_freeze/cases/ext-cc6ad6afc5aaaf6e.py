def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        user=dict(required=False, type='str'),
        object_id=dict(required=True, type='int'),
        role_definition=dict(required=True, type='str'),
        object_ansible_id=dict(required=False, type='int'),
        user_ansible_id=dict(required=False, type='int'),
        state=dict(default='present', choices=['present', 'absent']),
    )

    module = ControllerAPIModule(argument_spec=argument_spec)

    user = module.params.get('user')
    object_id = module.params.get('object_id')
    role_definition_str = module.params.get('role_definition')
    object_ansible_id = module.params.get('object_ansible_id')
    user_ansible_id = module.params.get('user_ansible_id')
    state = module.params.get('state')

    role_definition = module.get_one('role_definitions', allow_none=False, name_or_id=role_definition_str)
    user = module.get_one('users', allow_none=False, name_or_id=user)

    kwargs = {
        'role_definition': role_definition['id'],
        'object_id': object_id,
        'user': user['id'],
        'object_ansible_id': object_ansible_id,
        'user_ansible_id': user_ansible_id,
    }

    # get rid of None type values
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    role_user_assignment = module.get_one('role_user_assignments', **{'data': kwargs})

    if state == 'absent':
        module.delete_if_needed(
            role_user_assignment,
            item_type='role_user_assignment',
        )

    if state == 'present':
        module.create_if_needed(
            role_user_assignment,
            kwargs,
            endpoint='role_user_assignments',
            item_type='role_user_assignment',
        )
