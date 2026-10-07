# BIZPROOF V0.13 — Generic Certification Engine

V0.13 unifies the semantic capabilities developed through V0.12 behind
a generic source-level certification engine.

Target interface:

    python -m bizproof.universal_certifier \
        --source-file <file.py> \
        --case-id <id> \
        --output <evidence.json>

Pipeline:

Source
→ context extraction
→ capability resolution
→ semantic projection
→ concrete replay
→ mutant construction
→ formal refutation
→ verdict
→ evidence

The frozen 120-case external holdout is forbidden during V0.13
development. It can only be executed after the V0.13 engine itself is
frozen.
