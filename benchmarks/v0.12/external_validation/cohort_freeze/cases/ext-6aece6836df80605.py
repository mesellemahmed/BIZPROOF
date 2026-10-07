def parse(path, hatch_metadata):
    reqs = {}
    for line in hatch_metadata.read_requirements(Path(path).read_text()):
        req = Requirement(line)
        reqs[req.name.lower().replace('_', '-')] = req
    return reqs
