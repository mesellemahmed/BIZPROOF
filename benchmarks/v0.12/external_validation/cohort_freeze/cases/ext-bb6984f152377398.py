def _normalize_trust_expires_at(trust):
    # correct isotime
    if trust.get('expires_at') is not None:
        trust['expires_at'] = utils.isotime(
            trust['expires_at'], subsecond=True
        )
