from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .model import BusinessContract, InputSpec, TargetSpec


class ContractError(ValueError):
    pass


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be a mapping")
    return value


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field} must be a non-empty string")
    return value.strip()


def _resolve_source(contract_path: Path, source_raw: str) -> Path:
    raw_path = Path(source_raw)
    if raw_path.is_absolute():
        source = raw_path.resolve()
        if source.exists():
            return source
        raise ContractError(f"target source does not exist: {source}")

    for base in contract_path.parent.parents:
        candidate = (base / raw_path).resolve()
        if candidate.exists():
            return candidate

    candidate = (contract_path.parent / raw_path).resolve()
    if candidate.exists():
        return candidate

    raise ContractError(
        f"target source does not exist relative to contract ancestors: {source_raw}"
    )


def load_contract(path: str | Path) -> BusinessContract:
    contract_path = Path(path).resolve()
    raw = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    root = _require_mapping(raw, "contract")

    contract_id = _require_string(root.get("id"), "id")
    title = _require_string(root.get("title"), "title")

    target_raw = _require_mapping(root.get("target"), "target")
    source_raw = _require_string(target_raw.get("source"), "target.source")
    function = _require_string(target_raw.get("function"), "target.function")
    source = _resolve_source(contract_path, source_raw)

    inputs_raw = _require_mapping(root.get("inputs"), "inputs")
    inputs: list[InputSpec] = []

    for name, spec_value in inputs_raw.items():
        spec = _require_mapping(spec_value, f"inputs.{name}")
        type_name = _require_string(spec.get("type"), f"inputs.{name}.type")
        if type_name not in {"int", "bool"}:
            raise ContractError(f"inputs.{name}.type must be one of: int, bool")

        minimum = spec.get("min")
        maximum = spec.get("max")
        if type_name == "int":
            if not isinstance(minimum, int) or not isinstance(maximum, int):
                raise ContractError(f"integer input {name} requires integer min and max")
            if minimum > maximum:
                raise ContractError(f"inputs.{name}.min must be <= max")

        label = spec.get("label")
        if label is not None and not isinstance(label, str):
            raise ContractError(f"inputs.{name}.label must be a string")

        inputs.append(
            InputSpec(
                name=str(name),
                type_name=type_name,
                minimum=minimum,
                maximum=maximum,
                label=label,
            )
        )

    precondition = _require_string(root.get("precondition", "True"), "precondition")
    postcondition = _require_string(root.get("postcondition"), "postcondition")

    business_raw = root.get("business", {})
    business = _require_mapping(business_raw, "business")
    expected_outcome = business.get("expected_outcome")
    if expected_outcome is not None and not isinstance(expected_outcome, str):
        raise ContractError("business.expected_outcome must be a string")

    return BusinessContract(
        contract_id=contract_id,
        title=title,
        target=TargetSpec(source=source, function=function),
        inputs=tuple(inputs),
        precondition=precondition,
        postcondition=postcondition,
        expected_outcome=expected_outcome,
    )
