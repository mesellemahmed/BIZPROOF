def build_permission_filter(
    schema: tantivy.Schema,
    user: AbstractUser,
    viewer_group_ids: Iterable[int] = (),
) -> tantivy.Query:
    """
    Build a query filter for user document permissions.

    Creates a query that matches only documents visible to the specified user
    according to paperless-ngx permission rules:
    - Public documents (no owner) are visible to all users
    - Private documents are visible to their owner
    - Documents explicitly shared with the user are visible
    - Documents shared with one of the user's current groups are visible

    Args:
        schema: Tantivy schema for field validation
        user: User to check permissions for
        viewer_group_ids: Current group memberships for the user

    Returns:
        Tantivy query that filters results to visible documents
    """
    owner_any = tantivy.Query.exists_query("owner_id")
    no_owner = tantivy.Query.boolean_query(
        [
            (tantivy.Occur.Must, tantivy.Query.all_query()),
            (tantivy.Occur.MustNot, owner_any),
        ],
    )
    owned = tantivy.Query.term_query(schema, "owner_id", user.pk)
    shared = tantivy.Query.term_query(schema, "viewer_id", user.pk)
    group_shared = [
        tantivy.Query.term_query(schema, "viewer_group_id", group_id)
        for group_id in viewer_group_ids
    ]
    return tantivy.Query.disjunction_max_query(
        [no_owner, owned, shared, *group_shared],
    )
