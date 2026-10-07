from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


CASE_COUNT = 60

EXPECTED_CASE_MAP_SHA256 = "e4a836cade875da20e736cde6e300c8d5f82c4b342f3f60f7d6895f194120f3f"

EXPECTED_ORDER_SHA256 = "ca74897a6d997db81e32fab369f806a6956365c3a9d07ab59aae681d063bc423"

EXPECTED_ENGINE_MANIFEST_SHA256 = "23651f8fe4fa97c848ab3912f7b678c0b4674fd277bcdb80b7eaeb2b14c04ee3"


ALLOWED_SCIENTIFIC_OUTCOMES = {
    "CERTIFIED_A1",
    "CERTIFIED_A2",
    "AMBIGUOUS",
    "UNSUPPORTED",
}


def _sha256_bytes(
    value: bytes,
) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(
    path: Path,
) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_jsonl(
    path: Path,
) -> list[JsonDict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _atomic_json(
    path: Path,
    payload: JsonDict,
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(
        temporary,
        path,
    )


def _append_jsonl(
    path: Path,
    payload: JsonDict,
) -> None:
    with path.open(
        "a",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        handle.write(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            + "\n"
        )

        handle.flush()
        os.fsync(handle.fileno())


def _validate_case_map(
    path: Path,
) -> list[JsonDict]:
    actual_hash = _sha256_file(path)

    if actual_hash != EXPECTED_CASE_MAP_SHA256:
        raise RuntimeError(f"case_map_sha256_mismatch:{actual_hash}")

    rows = _read_jsonl(path)

    if len(rows) != CASE_COUNT:
        raise RuntimeError(f"case_map_count_mismatch:{len(rows)}")

    expected_order = list(
        range(
            1,
            CASE_COUNT + 1,
        )
    )

    actual_order = [int(row["evaluation_order"]) for row in rows]

    if actual_order != expected_order:
        raise RuntimeError("evaluation_order_not_exact")

    case_ids = [str(row["case_id"]) for row in rows]

    if len(set(case_ids)) != CASE_COUNT:
        raise RuntimeError("duplicate_case_ids")

    order_payload = "\n".join(case_ids) + "\n"

    order_sha = _sha256_bytes(order_payload.encode("utf-8"))

    if order_sha != EXPECTED_ORDER_SHA256:
        raise RuntimeError(f"evaluation_order_sha256_mismatch:{order_sha}")

    return rows


def _validate_engine_manifest(
    manifest_path: Path,
) -> None:
    actual_manifest_sha = _sha256_file(manifest_path)

    if actual_manifest_sha != EXPECTED_ENGINE_MANIFEST_SHA256:
        raise RuntimeError(f"engine_manifest_sha256_mismatch:{actual_manifest_sha}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for item in manifest["files"]:
        path = Path(item["path"])

        if not path.is_file():
            raise RuntimeError("engine_file_missing:" + str(path))

        actual = _sha256_file(path)

        if actual != item["sha256"]:
            raise RuntimeError("engine_file_sha256_mismatch:" + str(path))


def _validate_sources(
    *,
    rows: list[JsonDict],
    cohort_root: Path,
) -> None:
    for row in rows:
        case_id = str(row["case_id"])

        path = cohort_root / "cases" / f"{case_id}.py"

        if not path.is_file():
            raise RuntimeError("case_missing:" + case_id)

        actual = _sha256_file(path)

        expected = str(row["source_sha256"])

        if actual != expected:
            raise RuntimeError("case_sha256_mismatch:" + case_id)


def _formal_obligation_count(
    result: JsonDict,
) -> int:
    obligations = result.get("formal_obligations")

    if isinstance(
        obligations,
        list,
    ):
        return len(obligations)

    for key in (
        "formal_obligation_count",
        "formal_obligations_attempted",
    ):
        value = result.get(key)

        if (
            isinstance(
                value,
                int,
            )
            and not isinstance(
                value,
                bool,
            )
            and value >= 0
        ):
            return value

    return 0


def _a2_obligation_count(
    result: JsonDict,
) -> int:
    value = result.get("a2_obligation_count")

    if (
        isinstance(value, int)
        and not isinstance(
            value,
            bool,
        )
        and value >= 0
    ):
        return value

    return 0


def _scientific_record(
    *,
    row: JsonDict,
    result: JsonDict,
    runtime_seconds: float,
) -> JsonDict:
    outcome = result.get("scientific_outcome")

    certified = result.get("certified")

    if (
        not isinstance(
            outcome,
            str,
        )
        or outcome not in ALLOWED_SCIENTIFIC_OUTCOMES
    ):
        return _infra_record(
            row=row,
            error_type=("InvalidScientificOutcome"),
            error_message=str(outcome),
            runtime_seconds=(runtime_seconds),
            engine_result=result,
        )

    expected_certified = outcome in {
        "CERTIFIED_A1",
        "CERTIFIED_A2",
    }

    if (
        not isinstance(
            certified,
            bool,
        )
        or certified != expected_certified
    ):
        return _infra_record(
            row=row,
            error_type=("InvalidCertifiedFlag"),
            error_message=(f"outcome={outcome!r},certified={certified!r}"),
            runtime_seconds=(runtime_seconds),
            engine_result=result,
        )

    hardened = result.get("v014_osss_hardened", {})

    hardened_active = bool(
        isinstance(
            hardened,
            dict,
        )
        and hardened.get("active") is True
    )

    return {
        "schema_version": "BIZPROOF-V0.14-CONFIRMATORY60-RAW-1",
        "evaluation_order": int(row["evaluation_order"]),
        "case_id": str(row["case_id"]),
        "project": str(row["project"]),
        "project_commit": str(row["project_commit"]),
        "stratum": str(row["stratum"]),
        "source_sha256": str(row["source_sha256"]),
        "record_kind": "SCIENTIFIC_RESULT",
        "scientific_outcome": outcome,
        "certified": certified,
        "a_level": result.get("a_level"),
        "reason_code": str(
            result.get(
                "reason_code",
                "NONE",
            )
        ),
        "reason": str(
            result.get(
                "reason",
                "NONE",
            )
        ),
        "formal_obligation_count": _formal_obligation_count(result),
        "a2_obligation_count": _a2_obligation_count(result),
        "hardened_osss_active": hardened_active,
        "runtime_seconds": runtime_seconds,
        "runtime_role": "DESCRIPTIVE_ONLY",
        "engine_result": result,
    }


def _infra_record(
    *,
    row: JsonDict,
    error_type: str,
    error_message: str,
    runtime_seconds: float | None,
    engine_result: JsonDict | None = None,
) -> JsonDict:
    return {
        "schema_version": "BIZPROOF-V0.14-CONFIRMATORY60-RAW-1",
        "evaluation_order": int(row["evaluation_order"]),
        "case_id": str(row["case_id"]),
        "project": str(row["project"]),
        "project_commit": str(row["project_commit"]),
        "stratum": str(row["stratum"]),
        "source_sha256": str(row["source_sha256"]),
        "record_kind": "INFRA_ERROR",
        "scientific_outcome": "INFRA_ERROR",
        "certified": False,
        "a_level": None,
        "reason_code": ("INFRA::" + error_type),
        "reason": error_message,
        "formal_obligation_count": 0,
        "a2_obligation_count": 0,
        "hardened_osss_active": False,
        "runtime_seconds": runtime_seconds,
        "runtime_role": "DESCRIPTIVE_ONLY",
        "infra_error_type": error_type,
        "engine_result": engine_result,
    }


def _validate_existing_prefix(
    *,
    raw_path: Path,
    rows: list[JsonDict],
) -> list[JsonDict]:
    if not raw_path.exists():
        return []

    existing = _read_jsonl(raw_path)

    if len(existing) > CASE_COUNT:
        raise RuntimeError("raw_record_overflow")

    for index, record in enumerate(existing):
        expected = rows[index]

        if int(record["evaluation_order"]) != index + 1:
            raise RuntimeError("raw_order_mismatch")

        if record["case_id"] != expected["case_id"]:
            raise RuntimeError("raw_case_prefix_mismatch")

        if record["source_sha256"] != expected["source_sha256"]:
            raise RuntimeError("raw_source_prefix_mismatch")

    return existing


def _default_state() -> JsonDict:
    return {
        "schema_version": "BIZPROOF-V0.14-CONFIRMATORY60-RUN-STATE-1",
        "status": "RUNNING",
        "next_index": 0,
        "active_case_id": None,
        "resume_count": 0,
        "case_count": CASE_COUNT,
    }


def _load_state(
    path: Path,
) -> JsonDict:
    return json.loads(path.read_text(encoding="utf-8"))


def _recover_interrupted_case(
    *,
    rows: list[JsonDict],
    raw_path: Path,
    state_path: Path,
    state: JsonDict,
) -> JsonDict:
    active = state.get("active_case_id")

    if active is None:
        return state

    next_index = int(state["next_index"])

    existing = _validate_existing_prefix(
        raw_path=raw_path,
        rows=rows,
    )

    # Record was already durably written, but the state update
    # was interrupted. Never duplicate or re-execute it.
    if len(existing) == (next_index + 1):
        last = existing[-1]

        if last["case_id"] != active:
            raise RuntimeError("active_case_raw_mismatch")

        state["next_index"] = next_index + 1

        state["active_case_id"] = None

        _atomic_json(
            state_path,
            state,
        )

        return state

    # Case execution began but no durable raw record exists.
    # At-most-once semantics: classify interruption as infra,
    # NEVER rerun that case.
    if len(existing) == next_index:
        row = rows[next_index]

        if row["case_id"] != active:
            raise RuntimeError("active_case_state_mismatch")

        record = _infra_record(
            row=row,
            error_type=("InterruptedExecution"),
            error_message=(
                "runner process interrupted after case start and before durable raw record"
            ),
            runtime_seconds=None,
        )

        _append_jsonl(
            raw_path,
            record,
        )

        state["next_index"] = next_index + 1

        state["active_case_id"] = None

        _atomic_json(
            state_path,
            state,
        )

        return state

    raise RuntimeError("cannot_reconcile_interrupted_state")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case-map",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cohort-root",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--engine-manifest",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--raw-dir",
        type=Path,
    )

    parser.add_argument(
        "--verify-only",
        action="store_true",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    args = parser.parse_args()

    rows = _validate_case_map(args.case_map)

    _validate_engine_manifest(args.engine_manifest)

    _validate_sources(
        rows=rows,
        cohort_root=(args.cohort_root),
    )

    if args.verify_only:
        print("confirmatory cases verified = 60 / 60")
        print("engine byte identity        = PASS")
        print("scientific execution        = 0")
        print("verify-only                 = PASS")
        return

    if args.raw_dir is None:
        raise SystemExit("--raw-dir is required for execution")

    raw_dir: Path = args.raw_dir

    raw_path = raw_dir / "raw_results.jsonl"

    state_path = raw_dir / "run_state.json"

    if not args.resume:
        if raw_dir.exists():
            raise RuntimeError("raw_directory_already_exists;refusing_possible_rerun")

        raw_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        state = _default_state()

        _atomic_json(
            state_path,
            state,
        )

    else:
        if not state_path.is_file():
            raise RuntimeError("resume_state_missing")

        state = _load_state(state_path)

        if state.get("status") == "COMPLETE":
            raise RuntimeError("run_already_complete;rerun_forbidden")

        resume_count = int(
            state.get(
                "resume_count",
                0,
            )
        )

        if resume_count >= 2:
            raise RuntimeError("maximum_process_resumes_exceeded")

        state["resume_count"] = resume_count + 1

        _atomic_json(
            state_path,
            state,
        )

        state = _recover_interrupted_case(
            rows=rows,
            raw_path=raw_path,
            state_path=state_path,
            state=state,
        )

    existing = _validate_existing_prefix(
        raw_path=raw_path,
        rows=rows,
    )

    next_index = int(state["next_index"])

    if len(existing) != next_index:
        raise RuntimeError("state_raw_prefix_mismatch")

    # Import only after every pre-execution integrity gate passes.
    from bizproof.v014_osss_hardened import (
        certify_v014_osss_hardened,
    )

    for zero_index in range(
        next_index,
        CASE_COUNT,
    ):
        row = rows[zero_index]

        case_id = str(row["case_id"])

        source_path = args.cohort_root / "cases" / f"{case_id}.py"

        # Durable "case started" marker.
        state["next_index"] = zero_index

        state["active_case_id"] = case_id

        _atomic_json(
            state_path,
            state,
        )

        start = time.perf_counter()

        try:
            with tempfile.TemporaryDirectory(prefix=("bizproof-v014-confirmatory-")) as temporary:
                temporary_path = Path(temporary) / f"{case_id}.py"

                # Exact bytes. No runner-level normalization.
                temporary_path.write_bytes(source_path.read_bytes())

                result = certify_v014_osss_hardened(
                    source_file=(temporary_path),
                    evidence_id=("v014-confirmatory60::" + case_id),
                )

            runtime = time.perf_counter() - start

            if not isinstance(
                result,
                dict,
            ):
                record = _infra_record(
                    row=row,
                    error_type=("NonMappingEngineResult"),
                    error_message=(type(result).__name__),
                    runtime_seconds=(runtime),
                )

            else:
                record = _scientific_record(
                    row=row,
                    result=result,
                    runtime_seconds=(runtime),
                )

        except Exception as exc:
            runtime = time.perf_counter() - start

            record = _infra_record(
                row=row,
                error_type=(type(exc).__name__),
                error_message=str(exc),
                runtime_seconds=(runtime),
                engine_result={
                    "traceback": traceback.format_exc(),
                },
            )

        _append_jsonl(
            raw_path,
            record,
        )

        # Only after raw record is durable.
        state["next_index"] = zero_index + 1

        state["active_case_id"] = None

        _atomic_json(
            state_path,
            state,
        )

        print(
            f"{zero_index + 1:03d}/060 {case_id} RECORDED",
            flush=True,
        )

    final_records = _validate_existing_prefix(
        raw_path=raw_path,
        rows=rows,
    )

    if len(final_records) != CASE_COUNT:
        raise RuntimeError("final_raw_count_mismatch")

    state["status"] = "COMPLETE"

    state["next_index"] = CASE_COUNT

    state["active_case_id"] = None

    state["raw_sha256"] = _sha256_file(raw_path)

    _atomic_json(
        state_path,
        state,
    )

    print()
    print("raw records = 60 / 60")

    print(
        "raw SHA-256 =",
        state["raw_sha256"],
    )

    print("scientific outcomes were recorded but NOT summarized")

    print("next required action = FREEZE RAW BEFORE ANALYSIS")


if __name__ == "__main__":
    main()
