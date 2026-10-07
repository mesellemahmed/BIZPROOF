def delete_id_mapping(self, public_id):
    with sql.session_for_write() as session:
        try:
            session.query(IDMapping).filter(
                IDMapping.public_id == public_id
            ).delete()
        except sql.NotFound:  # nosec
            # NOTE(morganfainberg): There is nothing to delete and nothing
            # to do.
            pass
