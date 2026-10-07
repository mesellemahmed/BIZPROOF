def _create_policy_store(client: BaseClient, args) -> tuple[str | None, bool]:
    """
    Create if needed the policy store.

    This function returns two elements:
    - the policy store ID
    - whether the policy store ID returned refers to a newly created policy store.
    """
    paginator = client.get_paginator("list_policy_stores")
    pages = paginator.paginate()
    policy_stores = [application for page in pages for application in page["policyStores"]]
    existing_policy_stores = [
        policy_store
        for policy_store in policy_stores
        if policy_store.get("description") == args.policy_store_description
    ]

    log.debug("Policy stores found: %s", policy_stores)
    log.debug("Existing policy stores found: %s", existing_policy_stores)

    if len(existing_policy_stores) > 0:
        print(
            f"There is already a policy store with description '{args.policy_store_description}' in Amazon Verified Permissions: '{existing_policy_stores[0]['policyStoreId']}'."
        )
        return existing_policy_stores[0]["policyStoreId"], False
    print(f"No policy store with description '{args.policy_store_description}' found, creating one.")
    if args.dry_run:
        print(f"Dry run, not creating the policy store with description '{args.policy_store_description}'.")
        return None, True

    response = client.create_policy_store(
        validationSettings={
            "mode": "STRICT",
        },
        description=args.policy_store_description,
    )
    log.debug("Response from create_policy_store: %s", response)

    print(f"Policy store created: '{response['policyStoreId']}'")

    return response["policyStoreId"], True
