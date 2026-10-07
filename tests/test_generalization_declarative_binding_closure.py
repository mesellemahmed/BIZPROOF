from __future__ import annotations

import importlib
from typing import Any


def _module() -> Any:

    return importlib.import_module("bizproof.generalization_declarative_binding_closure")


def test_binding_subject_function_parameter() -> None:

    module = _module()

    occurrence = {
        "resolution_status": "FUNCTION_PARAMETER_BOUNDARY",
        "authoritative_binding": {
            "parameter": "individu",
        },
    }

    assert module._binding_subject(occurrence) == "individu"


def test_binding_subject_parameter_method() -> None:

    module = _module()

    occurrence = {
        "resolution_status": "PARAMETER_METHOD_BOUNDARY",
        "authoritative_binding": {
            "receiver_root": "individu",
        },
    }

    assert module._binding_subject(occurrence) == "individu"


def test_binding_id_stable() -> None:

    module = _module()

    first = module._binding_id(
        candidate_id="candidate",
        primitive="individu",
        resolution_status="FUNCTION_PARAMETER_BOUNDARY",
        subject="individu",
        source_expression="individu('age', period)",
    )

    second = module._binding_id(
        candidate_id="candidate",
        primitive="individu",
        resolution_status="FUNCTION_PARAMETER_BOUNDARY",
        subject="individu",
        source_expression="individu('age', period)",
    )

    assert first == second

    assert first.startswith("DB-")


def test_probe_status_aliases() -> None:

    module = _module()

    assert (
        module._probe_status(
            {
                "status": "SYMBOLIC_FRONTEND_READY",
            }
        )
        == "SYMBOLIC_FRONTEND_READY"
    )


def test_workplan_route_aliases() -> None:

    module = _module()

    assert (
        module._workplan_route(
            {
                "route": "BINDING_DEFINITION",
            }
        )
        == "BINDING_DEFINITION"
    )


def test_checkout_verification_manifest(
    tmp_path: Any,
) -> None:

    module = _module()

    import hashlib
    import json

    payload = {
        "generated_by": "HOST_GIT_PREFLIGHT",
        "structural_candidate_count": 11,
        "source_ids": [
            "openfisca_france",
        ],
        "records": [
            {
                "source_id": "openfisca_france",
                "expected_commit": "abc123",
                "actual_commit": "abc123",
                "passed": True,
            },
        ],
        "all_passed": True,
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=True,
    )

    payload["manifest_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    path = tmp_path / "checkout.json"

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    result = module._checkout_verification_map(path)

    assert set(result) == {
        "openfisca_france",
    }

    assert result["openfisca_france"]["passed"] is True
