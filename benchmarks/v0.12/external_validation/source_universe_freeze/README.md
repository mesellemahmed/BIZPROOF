# BIZPROOF V0.12 — External Source Universe Freeze

## Purpose

This freeze defines the complete prospective repository universe used
for external project selection.

No BIZPROOF external certification outcome has been observed.

## Universe

The universe contains 18 public Python-oriented software repositories.

The repositories span multiple software domains including enterprise
applications, commerce, networking, monitoring, document management,
content management, data management, messaging, analytics, identity,
cloud management, workflow automation, and IoT automation.

Each repository is frozen by its exact Git commit before project
ranking or function selection.

## Relation to E0

E0 requires 12 unseen projects and deterministic project selection.

E1A provides 18 frozen candidate projects.

E1B must:

1. materialize exactly the frozen repository commits;
2. compute deterministic Python-source snapshot identities;
3. exclude historical project and exact-source overlap;
4. rank all eligible projects using the E0 project-selection seed;
5. select exactly the first 12 eligible projects;
6. classify eligible functions using source shape only;
7. select exactly 10 functions per project using the frozen
   stratified deterministic rule;
8. freeze all 120 source bodies before BIZPROOF execution.

The six projects not selected by deterministic ranking remain part of
the frozen universe and cannot be substituted based on certification
difficulty or outcomes.

## Anti-bias rule

No repository may be added to or removed from this E1A universe after
project/function outcomes are observed.

If fewer than 12 projects satisfy the already-frozen E0 eligibility
criteria, external evaluation must stop and the protocol limitation
must be reported rather than silently replacing projects.

## Status

- source universe: FROZEN;
- exact repository commits: FROZEN;
- external projects selected: NO;
- external functions selected: NO;
- external cohort frozen: NO;
- BIZPROOF external execution: NOT STARTED;
- external outcomes observed: NONE.
