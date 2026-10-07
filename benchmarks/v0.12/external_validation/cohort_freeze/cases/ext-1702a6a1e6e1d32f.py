def _execute(q: Select[Any], table: Table, context: Context) -> Any:
    '''
    Takes an SqlAlchemy query (q) that is (at its base) a Select on an
    object table (table), and it returns the object.

    Analogous with _execute_with_revision, so takes the same params, even
    though it doesn't need the table.
    '''
    session = model.Session
    result: Any = session.execute(q)
    return result
