def get_device(session: Session, request: Request) -> Device:
    """
    :return: dict that corresponds to the current device
    """
    # TODO (v20): remove backward compatibility
    if '_devices' not in session:
        session['_devices'] = {}
        session.is_dirty = True

    ip_address = request.httprequest.remote_addr
    ip_address_key = collapse_ip_address(ip_address)
    user_agent = request.httprequest.user_agent.string
    # No collision with different IP addresses
    device_key = f'{ip_address_key.encode().hex()}{adler32(user_agent.encode()):x}'

    with suppress(KeyError):
        return session['_devices'][device_key]

    geoip = GeoIP(ip_address)

    session['_devices'][device_key] = new_device = {
        'ip_address': ip_address_key,
        'user_agent': user_agent,
        'first_activity': int(datetime.now().timestamp()),
        'last_activity': None,
        'country': geoip.country.name,
        'city': geoip.city.name,
        'trusted': not session['_devices'],  # First device in a session is always trusted
    }
    session.is_dirty = True
    return new_device
