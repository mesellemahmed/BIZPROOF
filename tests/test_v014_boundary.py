from __future__ import annotations

from pathlib import Path

from bizproof.v014_boundary import (
    certify_v014,
    prepare_boundary_source,
)


def _write(
    tmp_path: Path,
    text: str,
) -> Path:
    path = tmp_path / "candidate.py"

    path.write_text(
        text,
        encoding="utf-8",
    )

    return path


def test_keyword_only_binding(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    x: int,
    *,
    limit: int,
) -> int:
    return x + limit
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::keyword-only"),
    )

    assert result["scientific_outcome"] == "CERTIFIED_A1"

    assert result["certified"] is True


def test_external_numeric_call(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    return x + external_price(x)
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::external-call"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    bindings = result["v014_boundary"]["bindings"]

    assert len(bindings) == 1

    assert bindings[0]["kind"] == "OPAQUE_CALL_RESULT"


def test_external_predicate_call(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> bool:
    return external_allowed(x) and x > 0
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::predicate-call"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_standalone_external_effect(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    audit(x)
    return x + 1
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::effect"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    effects = result["v014_boundary"]["effects"]

    assert effects


def test_parameter_subscript_read(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    order,
    x: int,
) -> bool:
    return order["active"] and x > 0
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::subscript"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    kinds = {item["kind"] for item in result["v014_boundary"]["bindings"]}

    assert "OPAQUE_SUBSCRIPT_READ" in kinds


def test_unused_variadic_removed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    x: int,
    *args,
    **kwargs,
) -> int:
    return x + 1
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::unused-variadic"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_boundary_passthrough_rejected(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    return external_price(x)
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::passthrough"),
    )

    assert result["certified"] is False

    assert result["reason"] == "boundary_passthrough_only"


def test_loop_remains_unsupported(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    total = 0
    for value in range(x):
        total = total + value
    return total
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::loop"),
    )

    assert result["certified"] is False


def test_preparation_is_deterministic(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    return x + external_price(x)
""".strip()
        + "\n",
    )

    first = prepare_boundary_source(source_file=path)

    second = prepare_boundary_source(source_file=path)

    assert first == second


def test_no_case_specific_routing() -> None:
    source = Path("src/bizproof/v014_boundary.py").read_text(encoding="utf-8")

    forbidden = (
        "home-assistant/core",
        "saleor/saleor",
        "apache/airflow",
        "ext-",
        "TARGETS",
        "ADAPTERS",
    )

    for token in forbidden:
        assert token not in source


def test_v014_dedents_extracted_method(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
    def rule(
        self,
        x: int,
    ) -> int:
        return self.limit + x
""".strip("\n")
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::dedented-method"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"

    kinds = {item["kind"] for item in result["v014_boundary"]["bindings"]}

    assert "OPAQUE_ATTRIBUTE_READ" in kinds


def test_v014_effect_only_branch_keeps_valid_suite(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(x: int) -> int:
    if x > 0:
        audit(x)
    return x + 1
""".strip()
        + "\n",
    )

    preparation = prepare_boundary_source(source_file=path)

    compile(
        preparation.normalized_source,
        "<v014-prepared>",
        "exec",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::effect-branch"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_v014_parameter_attribute_predicate(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    user,
    enabled: bool,
) -> bool:
    return user.is_staff and enabled
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::attribute-predicate"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_v014_parameter_attribute_arithmetic(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    account,
    amount: int,
) -> int:
    return account.balance + amount
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::attribute-arithmetic"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_v014_method_callee_is_not_rewritten_as_value(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(
    service,
    x: int,
) -> int:
    return x + service.price(x)
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::method-boundary"),
    )

    assert result["certified"] is True
    assert result["a_level"] == "A1"


def test_v014_attribute_passthrough_still_rejected(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path,
        """
def rule(account) -> int:
    return account.balance
""".strip()
        + "\n",
    )

    result = certify_v014(
        source_file=path,
        evidence_id=("dev::attribute-passthrough"),
    )

    assert result["certified"] is False
    assert result["reason"] == "boundary_passthrough_only"
