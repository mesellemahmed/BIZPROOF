def expand_ipnetwork_pattern(string, family):
    """
    Expand an IP network pattern into a list of strings. Examples:
      '192.0.2.[1,2,100-250]/24' => ['192.0.2.1/24', '192.0.2.2/24', '192.0.2.100/24' ... '192.0.2.250/24']
      '2001:db8:0:[0,fd-ff]::/64' => ['2001:db8:0:0::/64', '2001:db8:0:fd::/64', ... '2001:db8:0:ff::/64']
    """
    if family not in [4, 6]:
        raise Exception("Invalid IP address family: {}".format(family))
    if family == 4:
        regex = IP4_EXPANSION_PATTERN
        base = 10
    else:
        regex = IP6_EXPANSION_PATTERN
        base = 16
    lead, pattern, remnant = re.split(regex, string, maxsplit=1)
    parsed_range = parse_numeric_range(pattern, base)
    for i in parsed_range:
        if re.search(regex, remnant):
            for string in expand_ipnetwork_pattern(remnant, family):
                yield ''.join([lead, format(i, 'x' if family == 6 else 'd'), string])
        else:
            yield ''.join([lead, format(i, 'x' if family == 6 else 'd'), remnant])
