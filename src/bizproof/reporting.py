from __future__ import annotations

import json
from typing import Any

from .model import BusinessContract, Evidence


def _label_map(contract: BusinessContract) -> dict[str, str]:
    return {
        spec.name: spec.label or spec.name.replace("_", " ").title() for spec in contract.inputs
    }


def render_text(contract: BusinessContract, evidence: Evidence) -> str:
    labels = _label_map(contract)

    lines = [
        f"Contract: {contract.contract_id} — {contract.title}",
        f"Status: {evidence.verdict.value}",
        f"Backend: {evidence.backend}",
    ]

    if evidence.counterexample:
        lines.append("")
        lines.append("Business counterexample:")
        for name, value in evidence.counterexample.items():
            lines.append(f"  {labels.get(name, name)}: {str(value).lower()}")

    if evidence.observed_result is not None:
        lines.append(f"  Observed result: {str(evidence.observed_result).lower()}")

    if evidence.postcondition_satisfied is not None:
        lines.append(
            f"  Business postcondition satisfied: {str(evidence.postcondition_satisfied).lower()}"
        )

    if evidence.replay_validated is not None:
        lines.append(f"  Concrete replay validated: {str(evidence.replay_validated).lower()}")

    if contract.expected_outcome and evidence.counterexample:
        lines.append(f"  Expected business rule: {contract.expected_outcome}")

    if evidence.reason_code:
        lines.append("")
        lines.append(f"Reason code: {evidence.reason_code}")
    if evidence.reason:
        lines.append(f"Reason: {evidence.reason}")

    if evidence.metadata:
        lines.append("")
        lines.append("Metadata:")
        for key, value in sorted(evidence.metadata.items()):
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def render_json(contract: BusinessContract, evidence: Evidence) -> str:
    payload: dict[str, Any] = {
        "contract_id": contract.contract_id,
        "title": contract.title,
        "verdict": evidence.verdict.value,
        "backend": evidence.backend,
        "counterexample": evidence.counterexample,
        "observed_result": evidence.observed_result,
        "postcondition_satisfied": evidence.postcondition_satisfied,
        "replay_validated": evidence.replay_validated,
        "reason_code": evidence.reason_code,
        "reason": evidence.reason,
        "metadata": evidence.metadata,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
