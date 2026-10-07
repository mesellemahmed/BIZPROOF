# V0.12-A — Authoritative Non-Scalar / Reference Audit

Frozen target population: 10.

No V0.12 recovery result has yet been assigned.

The initial keyword motif scan is not used for scientific classification because aggregate evidence files contain multiple candidate records and caused motif contamination.

## Frozen W19 reason-code distribution

- DOMAIN_OBJECT_RETURN: 1
- LIST_OF_DOMAIN_OBJECTS_RETURN: 1
- LIST_RETURN: 1
- OBJECT_RETURN: 1
- QUERYSET_RETURN: 1
- REFERENCE_DATE_OR_NONE: 1
- TEXT_RETURN: 3
- TUPLE_RETURN: 1

## Semantic families derived from the frozen reason codes

- DOMAIN_OBJECT_REFERENCE: 2
- FINITE_SEQUENCE_VALUE: 3
- OPTIONAL_REFERENCE_OR_DATE: 1
- QUERYSET_SUMMARY: 1
- TEXT_VALUE: 3

## Candidate mapping

### 0f73ae8d15cf3408

- source: pretix
- complexity: HIGH
- reason code: REFERENCE_DATE_OR_NONE
- semantic family: OPTIONAL_REFERENCE_OR_DATE
- reviewed reason: The result is a date/reference value or None, not a scalar business quantity.

### 26a1af8837fe7ae4

- source: pretix
- complexity: LOW
- reason code: TEXT_RETURN
- semantic family: TEXT_VALUE
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

### 6d009b7961c5d116

- source: django_oscar
- complexity: HIGH
- reason code: LIST_OF_DOMAIN_OBJECTS_RETURN
- semantic family: FINITE_SEQUENCE_VALUE
- reviewed reason: The reviewed source does not provide a defensible single scalar business-semantic projection under the frozen V0.11 A2 protocol.

### 6fd8bd69c26e7954

- source: pretix
- complexity: MEDIUM
- reason code: DOMAIN_OBJECT_RETURN
- semantic family: DOMAIN_OBJECT_REFERENCE
- reviewed reason: The reviewed source does not provide a defensible single scalar business-semantic projection under the frozen V0.11 A2 protocol.

### 75e61ddb4dde4f1a

- source: django_oscar
- complexity: MEDIUM
- reason code: TEXT_RETURN
- semantic family: TEXT_VALUE
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

### 87d2f0b3b15f0ea6

- source: django_oscar
- complexity: MEDIUM
- reason code: TEXT_RETURN
- semantic family: TEXT_VALUE
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

### 9cc9063a46d23cde

- source: pretix
- complexity: MEDIUM
- reason code: QUERYSET_RETURN
- semantic family: QUERYSET_SUMMARY
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

### d285ecd86455b150

- source: pretix
- complexity: MEDIUM
- reason code: TUPLE_RETURN
- semantic family: FINITE_SEQUENCE_VALUE
- reviewed reason: The reviewed source does not provide a defensible single scalar business-semantic projection under the frozen V0.11 A2 protocol.

### e1cf29f02fa0dadc

- source: django_oscar
- complexity: LOW
- reason code: LIST_RETURN
- semantic family: FINITE_SEQUENCE_VALUE
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

### fa377c649a747a7d

- source: django_oscar
- complexity: MEDIUM
- reason code: OBJECT_RETURN
- semantic family: DOMAIN_OBJECT_REFERENCE
- reviewed reason: The V1 function is AST-simple but its externally observable return semantics are not directly scalar. No scalar projection is certified without an additional business-semantic scope decision.

## V12-A3 implementation order

1. SYMBOLIC_TEXT_VALUE (3 candidates)

2. FINITE_STRUCTURED_SEQUENCE (3 candidates)

3. DOMAIN_OBJECT_REFERENCE (2 candidates)

4. OPTIONAL_REFERENCE_OR_DATE (1 candidates)

5. QUERYSET_SUMMARY (1 candidates)

The implementation order is an engineering prioritization.
It does not alter the frozen ten-candidate denominator.
