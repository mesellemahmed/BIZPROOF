from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import io
import json
import re
import subprocess
import sys
import textwrap
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_source(text: str) -> str:
    return textwrap.dedent(text).rstrip() + "\n"


def git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def git_text(repo: Path, *args: str) -> str:
    return git_bytes(repo, *args).decode(
        "utf-8",
        errors="strict",
    ).strip()


def tracked_python_files(repo: Path) -> list[str]:
    raw = git_bytes(
        repo,
        "ls-files",
        "-z",
        "--",
        "*.py",
    )

    return sorted(
        item.decode(
            "utf-8",
            errors="surrogateescape",
        )
        for item in raw.split(b"\0")
        if item
    )


def file_bytes(repo: Path, relative_path: str) -> bytes:
    local = repo / relative_path

    if local.is_file():
        return local.read_bytes()

    return git_bytes(
        repo,
        "show",
        f"HEAD:{relative_path}",
    )


def decode_python(data: bytes) -> str:
    readline = io.BytesIO(data).readline

    encoding, _ = tokenize.detect_encoding(
        readline
    )

    return data.decode(
        encoding
    )


def null_payload(*parts: str) -> bytes:
    return "\0".join(
        parts
    ).encode(
        "utf-8"
    )


def recursive_values(
    value: Any,
) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from recursive_values(
                child
            )

    elif isinstance(value, list):
        for child in value:
            yield from recursive_values(
                child
            )


def reconstruct_historical_hashes(
    roots: list[Path],
    exclude_part: str,
) -> set[str]:
    hashes: set[str] = set()

    for root in roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if exclude_part in path.parts:
                continue

            if path.suffix.lower() not in {
                ".json",
                ".jsonl",
            }:
                continue

            text = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            payloads: list[Any] = []

            if path.suffix.lower() == ".json":
                try:
                    payloads.append(
                        json.loads(text)
                    )
                except json.JSONDecodeError:
                    continue

            else:
                for line in text.splitlines():
                    if not line.strip():
                        continue

                    try:
                        payloads.append(
                            json.loads(line)
                        )
                    except json.JSONDecodeError:
                        continue

            for payload in payloads:
                for key, value in recursive_values(
                    payload
                ):
                    lower_key = key.lower()

                    if (
                        lower_key == "source"
                        and isinstance(
                            value,
                            str,
                        )
                    ):
                        hashes.add(
                            sha256_text(
                                canonical_source(
                                    value
                                )
                            )
                        )

                    if not isinstance(
                        value,
                        str,
                    ):
                        continue

                    candidate = value.lower()

                    if not HEX64.fullmatch(
                        candidate
                    ):
                        continue

                    source_or_body = (
                        "source" in lower_key
                        or "body" in lower_key
                    )

                    sha_or_hash = (
                        "sha" in lower_key
                        or "hash" in lower_key
                    )

                    if (
                        lower_key
                        in {
                            "source_sha256",
                            "body_sha256",
                            "sha256",
                        }
                        or (
                            source_or_body
                            and sha_or_hash
                        )
                    ):
                        hashes.add(
                            candidate
                        )

    return hashes


def excluded_path(
    relative_path: str,
    protocol: dict[str, Any],
) -> bool:
    path = Path(
        relative_path
    )

    lowered_parts = {
        part.lower()
        for part in path.parts
    }

    exclusions = protocol[
        "path_exclusion"
    ]

    if lowered_parts & set(
        exclusions[
            "excluded_parts"
        ]
    ):
        return True

    filename = path.name.lower()

    for pattern in exclusions[
        "excluded_filename_patterns"
    ]:
        if fnmatch.fnmatch(
            filename,
            pattern.lower(),
        ):
            return True

    return False


def generated_source(
    text: str,
    protocol: dict[str, Any],
) -> bool:
    header = "\n".join(
        text.splitlines()[:20]
    ).lower()

    return any(
        pattern.lower()
        in header
        for pattern
        in protocol[
            "path_exclusion"
        ][
            "generated_header_patterns"
        ]
    )


def is_notimplemented_raise(
    node: ast.stmt,
) -> bool:
    if not isinstance(
        node,
        ast.Raise,
    ):
        return False

    exc = node.exc

    if isinstance(
        exc,
        ast.Name,
    ):
        return exc.id in {
            "NotImplemented",
            "NotImplementedError",
        }

    if isinstance(
        exc,
        ast.Call,
    ) and isinstance(
        exc.func,
        ast.Name,
    ):
        return exc.func.id in {
            "NotImplemented",
            "NotImplementedError",
        }

    return False


def trivial_function(
    node: ast.FunctionDef
    | ast.AsyncFunctionDef,
) -> bool:
    body = node.body

    if len(body) != 1:
        return False

    item = body[0]

    if isinstance(
        item,
        ast.Pass,
    ):
        return True

    if (
        isinstance(
            item,
            ast.Expr,
        )
        and isinstance(
            item.value,
            ast.Constant,
        )
        and item.value.value
        is Ellipsis
    ):
        return True

    if is_notimplemented_raise(
        item
    ):
        return True

    return False


def candidate_nodes(
    tree: ast.Module,
) -> Iterable[
    tuple[
        str,
        ast.FunctionDef
        | ast.AsyncFunctionDef,
    ]
]:
    def walk_body(
        body: list[ast.stmt],
        prefix: tuple[str, ...],
    ) -> Iterable[
        tuple[
            str,
            ast.FunctionDef
            | ast.AsyncFunctionDef,
        ]
    ]:
        for node in body:
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                yield (
                    ".".join(
                        (
                            *prefix,
                            node.name,
                        )
                    ),
                    node,
                )

                # Deliberately do not recurse into a
                # function body: nested functions are
                # shape features, not independent cases.
                continue

            if isinstance(
                node,
                ast.ClassDef,
            ):
                yield from walk_body(
                    node.body,
                    (
                        *prefix,
                        node.name,
                    ),
                )

    yield from walk_body(
        tree.body,
        (),
    )


def call_name(
    node: ast.Call,
) -> str | None:
    if isinstance(
        node.func,
        ast.Name,
    ):
        return node.func.id

    if isinstance(
        node.func,
        ast.Attribute,
    ):
        return node.func.attr

    return None


def argument_names(
    node: ast.FunctionDef
    | ast.AsyncFunctionDef,
) -> set[str]:
    names = {
        arg.arg
        for arg in (
            node.args.posonlyargs
            + node.args.args
            + node.args.kwonlyargs
        )
    }

    if node.args.vararg:
        names.add(
            node.args.vararg.arg
        )

    if node.args.kwarg:
        names.add(
            node.args.kwarg.arg
        )

    names.discard(
        "self"
    )

    names.discard(
        "cls"
    )

    return names


def classify_shape(
    node: ast.FunctionDef
    | ast.AsyncFunctionDef,
    protocol: dict[str, Any],
) -> tuple[
    str,
    dict[str, Any],
]:
    shape = protocol[
        "shape_classification"
    ]

    descendants = list(
        ast.walk(node)
    )

    calls = [
        name
        for child in descendants
        if isinstance(
            child,
            ast.Call,
        )
        for name in [
            call_name(
                child
            )
        ]
        if name is not None
    ]

    call_set = set(
        calls
    )

    attrs = {
        child.attr
        for child in descendants
        if isinstance(
            child,
            ast.Attribute,
        )
    }

    args = argument_names(
        node
    )

    nested_defs = sum(
        isinstance(
            child,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
        for child in descendants
    ) - 1

    comprehensions = sum(
        isinstance(
            child,
            (
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        )
        for child in descendants
    )

    lambda_count = sum(
        isinstance(
            child,
            ast.Lambda,
        )
        for child in descendants
    )

    yield_count = sum(
        isinstance(
            child,
            (
                ast.Yield,
                ast.YieldFrom,
            ),
        )
        for child in descendants
    )

    attribute_writes = sum(
        isinstance(
            child,
            ast.Attribute,
        )
        and isinstance(
            child.ctx,
            (
                ast.Store,
                ast.Del,
            ),
        )
        for child in descendants
    )

    subscript_writes = sum(
        isinstance(
            child,
            ast.Subscript,
        )
        and isinstance(
            child.ctx,
            (
                ast.Store,
                ast.Del,
            ),
        )
        for child in descendants
    )

    container_nodes = sum(
        isinstance(
            child,
            (
                ast.Dict,
                ast.List,
                ast.Set,
                ast.Tuple,
            ),
        )
        for child in descendants
    )

    subscript_reads = sum(
        isinstance(
            child,
            ast.Subscript,
        )
        and isinstance(
            child.ctx,
            ast.Load,
        )
        for child in descendants
    )

    binding_names = set(
        shape[
            "S5_binding_argument_names"
        ]
    )

    domain_names = set(
        shape[
            "S5_domain_call_or_attribute_names"
        ]
    )

    effect_names = set(
        shape[
            "S4_effect_call_names"
        ]
    )

    ho_names = set(
        shape[
            "S3_higher_order_call_names"
        ]
    )

    container_call_names = set(
        shape[
            "S2_container_call_names"
        ]
    )

    s5 = bool(
        args
        & binding_names
    ) or bool(
        (
            call_set
            | attrs
        )
        & domain_names
    )

    s4 = (
        attribute_writes
        > 0
        or subscript_writes
        > 0
        or bool(
            call_set
            & effect_names
        )
    )

    s3 = (
        nested_defs
        > 0
        or comprehensions
        > 0
        or lambda_count
        > 0
        or yield_count
        > 0
        or bool(
            call_set
            & ho_names
        )
    )

    s2 = (
        container_nodes
        > 0
        or subscript_reads
        > 0
        or bool(
            call_set
            & container_call_names
        )
    )

    if s5:
        stratum = (
            "S5_BINDING_EXTERNAL_DOMAIN"
        )

    elif s4:
        stratum = (
            "S4_STATE_EFFECT"
        )

    elif s3:
        stratum = (
            "S3_NESTED_VECTOR_HIGHER_ORDER"
        )

    elif s2:
        stratum = (
            "S2_STRUCTURED_CONTAINER"
        )

    else:
        stratum = (
            "S1_LOCAL_SCALAR_CONTROL"
        )

    features = {
        "ast_nodes":
            len(
                descendants
            ),

        "arguments":
            sorted(
                args
            ),

        "call_count":
            len(
                calls
            ),

        "nested_defs":
            nested_defs,

        "comprehensions":
            comprehensions,

        "lambda_count":
            lambda_count,

        "yield_count":
            yield_count,

        "attribute_writes":
            attribute_writes,

        "subscript_writes":
            subscript_writes,

        "container_nodes":
            container_nodes,

        "subscript_reads":
            subscript_reads,
    }

    return (
        stratum,
        features,
    )


def source_interval(
    text: str,
    node: ast.FunctionDef
    | ast.AsyncFunctionDef,
) -> str:
    if node.end_lineno is None:
        raise ValueError(
            "AST node has no end_lineno"
        )

    lines = text.splitlines(
        keepends=True
    )

    raw = "".join(
        lines[
            node.lineno
            - 1:
            node.end_lineno
        ]
    )

    return canonical_source(
        raw
    )


def function_rank(
    protocol: dict[str, Any],
    project: str,
    relative_path: str,
    qname: str,
    source_sha: str,
) -> str:
    seed = protocol[
        "function_ranking"
    ][
        "seed"
    ]

    return sha256_bytes(
        null_payload(
            seed,
            project,
            relative_path,
            qname,
            source_sha,
        )
    )


def project_rank(
    protocol: dict[str, Any],
    project: str,
    snapshot_sha: str,
) -> str:
    seed = protocol[
        "project_ranking"
    ][
        "seed"
    ]

    return sha256_bytes(
        null_payload(
            seed,
            project,
            snapshot_sha,
        )
    )


def inventory_digest(
    candidates: list[
        dict[str, Any]
    ],
) -> str:
    lines = []

    for row in sorted(
        candidates,
        key=lambda item: (
            item[
                "function_rank"
            ],
            item[
                "relative_path"
            ],
            item[
                "qualified_name"
            ],
        ),
    ):
        lines.append(
            "\0".join(
                [
                    row[
                        "relative_path"
                    ],
                    row[
                        "qualified_name"
                    ],
                    row[
                        "source_sha256"
                    ],
                    row[
                        "stratum"
                    ],
                    row[
                        "function_rank"
                    ],
                ]
            )
            + "\n"
        )

    return sha256_text(
        "".join(
            lines
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--protocol",
        required=True,
    )

    parser.add_argument(
        "--source-manifest",
        required=True,
    )

    parser.add_argument(
        "--repos-root",
        required=True,
    )

    parser.add_argument(
        "--out",
        required=True,
    )

    parser.add_argument(
        "--historical-root",
        action="append",
        required=True,
    )

    args = parser.parse_args()

    protocol = json.loads(
        Path(
            args.protocol
        ).read_text(
            encoding="utf-8"
        )
    )

    source_manifest = json.loads(
        Path(
            args.source_manifest
        ).read_text(
            encoding="utf-8"
        )
    )

    repos_root = Path(
        args.repos_root
    )

    out = Path(
        args.out
    )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    cases_dir = out / "cases"

    cases_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    historical_hashes = (
        reconstruct_historical_hashes(
            [
                Path(item)
                for item
                in args.historical_root
            ],
            "external_validation",
        )
    )

    if not historical_hashes:
        raise RuntimeError(
            "historical source hash set is empty"
        )

    historical_hash_digest = (
        sha256_text(
            "\n".join(
                sorted(
                    historical_hashes
                )
            )
            + "\n"
        )
    )

    projects = source_manifest[
        "projects"
    ]

    if len(projects) != 6:
        raise RuntimeError(
            "expected 6 frozen reserve projects"
        )

    project_records: list[
        dict[str, Any]
    ] = []

    candidates_by_project: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = {}

    source_text_by_key: dict[
        tuple[
            str,
            str,
        ],
        str,
    ] = {}

    min_ast_nodes = protocol[
        "function_eligibility"
    ][
        "minimum_ast_nodes"
    ]

    for project in projects:
        identity = project[
            "canonical_project_identity"
        ]

        expected_commit = project[
            "frozen_git_commit"
        ]

        repo = (
            repos_root
            / identity.replace(
                "/",
                "__",
            )
        )

        if not repo.is_dir():
            raise RuntimeError(
                f"missing materialized repository: {identity}"
            )

        actual_commit = git_text(
            repo,
            "rev-parse",
            "HEAD",
        )

        if actual_commit != expected_commit:
            raise RuntimeError(
                (
                    f"commit mismatch {identity}: "
                    f"{actual_commit} != {expected_commit}"
                )
            )

        python_paths = (
            tracked_python_files(
                repo
            )
        )

        snapshot_records = []

        parse_failures = 0
        decode_failures = 0
        generated_files = 0
        excluded_files = 0
        functions_seen = 0
        trivial_functions = 0
        small_functions = 0
        historical_overlap = 0

        raw_candidates: list[
            dict[str, Any]
        ] = []

        for relative_path in python_paths:
            data = file_bytes(
                repo,
                relative_path,
            )

            file_sha = sha256_bytes(
                data
            )

            snapshot_records.append(
                (
                    relative_path,
                    file_sha,
                )
            )

            if excluded_path(
                relative_path,
                protocol,
            ):
                excluded_files += 1
                continue

            try:
                text = decode_python(
                    data
                )
            except Exception:
                decode_failures += 1
                continue

            if generated_source(
                text,
                protocol,
            ):
                generated_files += 1
                continue

            try:
                tree = ast.parse(
                    text,
                    filename=relative_path,
                )
            except SyntaxError:
                parse_failures += 1
                continue

            for qname, node in candidate_nodes(
                tree
            ):
                functions_seen += 1

                if trivial_function(
                    node
                ):
                    trivial_functions += 1
                    continue

                ast_nodes = sum(
                    1
                    for _ in ast.walk(
                        node
                    )
                )

                if ast_nodes < min_ast_nodes:
                    small_functions += 1
                    continue

                body = source_interval(
                    text,
                    node,
                )

                source_sha = sha256_text(
                    body
                )

                if (
                    source_sha
                    in historical_hashes
                ):
                    historical_overlap += 1
                    continue

                stratum, features = (
                    classify_shape(
                        node,
                        protocol,
                    )
                )

                rank = function_rank(
                    protocol,
                    identity,
                    relative_path,
                    qname,
                    source_sha,
                )

                record = {
                    "project":
                        identity,

                    "project_commit":
                        expected_commit,

                    "relative_path":
                        relative_path,

                    "qualified_name":
                        qname,

                    "source_sha256":
                        source_sha,

                    "stratum":
                        stratum,

                    "function_rank":
                        rank,

                    "features":
                        features,
                }

                raw_candidates.append(
                    record
                )

                source_text_by_key[
                    (
                        identity,
                        source_sha,
                    )
                ] = body

        snapshot_payload = "".join(
            path
            + "\0"
            + digest
            + "\n"
            for path, digest
            in sorted(
                snapshot_records
            )
        )

        snapshot_sha = sha256_text(
            snapshot_payload
        )

        rank = project_rank(
            protocol,
            identity,
            snapshot_sha,
        )

        # Deduplicate identical bodies inside one project.
        by_body: dict[
            str,
            dict[str, Any],
        ] = {}

        for candidate in raw_candidates:
            body_sha = candidate[
                "source_sha256"
            ]

            prior = by_body.get(
                body_sha
            )

            if (
                prior is None
                or candidate[
                    "function_rank"
                ]
                < prior[
                    "function_rank"
                ]
            ):
                by_body[
                    body_sha
                ] = candidate

        candidates = list(
            by_body.values()
        )

        for candidate in candidates:
            candidate[
                "project_snapshot_sha256"
            ] = snapshot_sha

            candidate[
                "project_rank"
            ] = rank

        candidates.sort(
            key=lambda item: (
                item[
                    "function_rank"
                ],
                item[
                    "relative_path"
                ],
                item[
                    "qualified_name"
                ],
            )
        )

        candidates_by_project[
            identity
        ] = candidates

        stratum_counts = Counter(
            item[
                "stratum"
            ]
            for item in candidates
        )

        eligible = (
            len(
                candidates
            )
            >= 10
        )

        record = {
            "canonical_project_identity":
                identity,

            "repository_url":
                project[
                    "repository_url"
                ],

            "domain_family":
                project[
                    "domain_family"
                ],

            "frozen_git_commit":
                expected_commit,

            "python_file_count":
                len(
                    python_paths
                ),

            "snapshot_sha256":
                snapshot_sha,

            "project_rank":
                rank,

            "functions_seen":
                functions_seen,

            "eligible_unique_functions":
                len(
                    candidates
                ),

            "eligible":
                eligible,

            "stratum_counts":
                dict(
                    sorted(
                        stratum_counts.items()
                    )
                ),

            "eligible_inventory_sha256":
                inventory_digest(
                    candidates
                ),

            "audit_counts": {
                "excluded_files":
                    excluded_files,

                "generated_files":
                    generated_files,

                "decode_failures":
                    decode_failures,

                "parse_failures":
                    parse_failures,

                "trivial_functions":
                    trivial_functions,

                "below_min_ast_nodes":
                    small_functions,

                "historical_body_overlap":
                    historical_overlap,

                "within_project_duplicate_bodies":
                    (
                        len(
                            raw_candidates
                        )
                        - len(
                            candidates
                        )
                    ),
            },
        }

        project_records.append(
            record
        )

    eligible_projects = sorted(
        (
            record
            for record in project_records
            if record[
                "eligible"
            ]
        ),
        key=lambda item: (
            item[
                "project_rank"
            ],
            item[
                "canonical_project_identity"
            ],
        ),
    )

    if len(
        eligible_projects
    ) < 6:
        raise RuntimeError(
            (
                "fewer than 6 frozen reserve projects satisfy the "
                "prospectively frozen eligibility rule"
            )
        )

    selected_projects = (
        eligible_projects[:6]
    )

    selected_project_ids = {
        item[
            "canonical_project_identity"
        ]
        for item
        in selected_projects
    }

    all_ranked_projects = sorted(
        project_records,
        key=lambda item: (
            not item[
                "eligible"
            ],
            item[
                "project_rank"
            ],
            item[
                "canonical_project_identity"
            ],
        ),
    )

    for record in all_ranked_projects:
        record[
            "selected"
        ] = (
            record[
                "canonical_project_identity"
            ]
            in selected_project_ids
        )

    selected_cases: list[
        dict[str, Any]
    ] = []

    selected_hashes_global: set[
        str
    ] = set()

    selection_audit = []

    strata_order = protocol[
        "within_project_selection"
    ][
        "strata_order"
    ]

    target_per_stratum = protocol[
        "within_project_selection"
    ][
        "target_per_stratum"
    ]

    per_project_target = protocol[
        "within_project_selection"
    ][
        "target"
    ]

    for project in selected_projects:
        identity = project[
            "canonical_project_identity"
        ]

        candidates = candidates_by_project[
            identity
        ]

        available = [
            item
            for item in candidates
            if item[
                "source_sha256"
            ]
            not in selected_hashes_global
        ]

        chosen: list[
            dict[str, Any]
        ] = []

        chosen_keys: set[
            tuple[
                str,
                str,
                str,
            ]
        ] = set()

        per_stratum_selected = {}

        for stratum in strata_order:
            pool = sorted(
                (
                    item
                    for item
                    in available
                    if item[
                        "stratum"
                    ]
                    == stratum
                ),
                key=lambda item: (
                    item[
                        "function_rank"
                    ],
                    item[
                        "relative_path"
                    ],
                    item[
                        "qualified_name"
                    ],
                ),
            )

            count = 0

            for item in pool:
                key = (
                    item[
                        "relative_path"
                    ],
                    item[
                        "qualified_name"
                    ],
                    item[
                        "source_sha256"
                    ],
                )

                if key in chosen_keys:
                    continue

                selected = dict(
                    item
                )

                selected[
                    "selection_reason"
                ] = (
                    "stratum_target:"
                    + stratum
                )

                chosen.append(
                    selected
                )

                chosen_keys.add(
                    key
                )

                count += 1

                if (
                    count
                    == target_per_stratum
                ):
                    break

            per_stratum_selected[
                stratum
            ] = count

        if len(
            chosen
        ) < per_project_target:

            remainder = sorted(
                available,
                key=lambda item: (
                    item[
                        "function_rank"
                    ],
                    item[
                        "relative_path"
                    ],
                    item[
                        "qualified_name"
                    ],
                ),
            )

            for item in remainder:
                key = (
                    item[
                        "relative_path"
                    ],
                    item[
                        "qualified_name"
                    ],
                    item[
                        "source_sha256"
                    ],
                )

                if key in chosen_keys:
                    continue

                selected = dict(
                    item
                )

                selected[
                    "selection_reason"
                ] = "deficit_fill"

                chosen.append(
                    selected
                )

                chosen_keys.add(
                    key
                )

                if (
                    len(
                        chosen
                    )
                    == per_project_target
                ):
                    break

        if len(
            chosen
        ) != per_project_target:
            raise RuntimeError(
                (
                    f"{identity} cannot supply "
                    f"{per_project_target} globally unique "
                    "functions under the frozen policy"
                )
            )

        duplicate_with_global = (
            selected_hashes_global
            & {
                item[
                    "source_sha256"
                ]
                for item in chosen
            }
        )

        if duplicate_with_global:
            raise RuntimeError(
                (
                    "global selected source-body "
                    f"duplicate in {identity}"
                )
            )

        for item in chosen:
            selected_hashes_global.add(
                item[
                    "source_sha256"
                ]
            )

        chosen.sort(
            key=lambda item: (
                item[
                    "function_rank"
                ],
                item[
                    "relative_path"
                ],
                item[
                    "qualified_name"
                ],
            )
        )

        selected_cases.extend(
            chosen
        )

        selection_audit.append(
            {
                "project":
                    identity,

                "eligible_available_after_global_dedup":
                    len(
                        available
                    ),

                "selected":
                    len(
                        chosen
                    ),

                "target_per_stratum_results":
                    per_stratum_selected,

                "deficit_fill_count":
                    sum(
                        item[
                            "selection_reason"
                        ]
                        == "deficit_fill"
                        for item in chosen
                    ),
            }
        )

    if len(
        selected_cases
    ) != 60:
        raise RuntimeError(
            "confirmatory cohort is not exactly 60 cases"
        )

    if len(
        selected_hashes_global
    ) != 60:
        raise RuntimeError(
            "selected source bodies are not globally unique"
        )

    project_rank_map = {
        item[
            "canonical_project_identity"
        ]:
            item[
                "project_rank"
            ]
        for item
        in selected_projects
    }

    selected_cases.sort(
        key=lambda item: (
            project_rank_map[
                item[
                    "project"
                ]
            ],
            item[
                "function_rank"
            ],
            item[
                "relative_path"
            ],
            item[
                "qualified_name"
            ],
        )
    )

    public_cases = []

    for index, item in enumerate(
        selected_cases,
        start=1,
    ):
        locator_payload = null_payload(
            "BIZPROOF-V014-CONFIRMATORY-CASE-1",
            item[
                "project"
            ],
            item[
                "relative_path"
            ],
            item[
                "qualified_name"
            ],
            item[
                "source_sha256"
            ],
        )

        case_id = (
            "ext-"
            + sha256_bytes(
                locator_payload
            )[:16]
        )

        body = source_text_by_key[
            (
                item[
                    "project"
                ],
                item[
                    "source_sha256"
                ],
            )
        ]

        body_path = (
            cases_dir
            / f"{case_id}.py"
        )

        body_path.write_text(
            body,
            encoding="utf-8",
        )

        if sha256_bytes(
            body_path.read_bytes()
        ) != item[
            "source_sha256"
        ]:
            raise RuntimeError(
                f"frozen body hash mismatch: {case_id}"
            )

        public = dict(
            item
        )

        public.pop(
            "features",
            None,
        )

        public[
            "case_id"
        ] = case_id

        public[
            "evaluation_index"
        ] = index

        public[
            "frozen_source_file"
        ] = (
            f"cases/{case_id}.py"
        )

        public[
            "external_outcome"
        ] = None

        public_cases.append(
            public
        )

    case_payload = [
        {
            key: row[
                key
            ]
            for key in (
                "case_id",
                "evaluation_index",
                "project",
                "project_commit",
                "project_snapshot_sha256",
                "relative_path",
                "qualified_name",
                "source_sha256",
                "stratum",
                "function_rank",
            )
        }
        for row in public_cases
    ]

    cohort_sha = sha256_text(
        json.dumps(
            case_payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )
    )

    project_distribution = Counter(
        row[
            "project"
        ]
        for row in public_cases
    )

    stratum_distribution = Counter(
        row[
            "stratum"
        ]
        for row in public_cases
    )

    if set(
        project_distribution.values()
    ) != {10}:
        raise RuntimeError(
            "not exactly 10 cases per project"
        )

    if len(
        project_distribution
    ) != 6:
        raise RuntimeError(
            "cohort does not contain 6 fixed reserve projects"
        )

    with (
        out
        / "selected_cases.jsonl"
    ).open(
        "w",
        encoding="utf-8",
    ) as fh:
        for row in public_cases:
            fh.write(
                json.dumps(
                    row,
                    sort_keys=True,
                )
                + "\n"
            )

    (
        out
        / "project_inventory.json"
    ).write_text(
        json.dumps(
            {
                "projects":
                    all_ranked_projects,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        out
        / "selected_projects.json"
    ).write_text(
        json.dumps(
            {
                "projects":
                    selected_projects,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        out
        / "selection_audit.json"
    ).write_text(
        json.dumps(
            {
                "projects":
                    selection_audit,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        out
        / "historical_hash_audit.json"
    ).write_text(
        json.dumps(
            {
                "historical_source_hash_count":
                    len(
                        historical_hashes
                    ),

                "historical_hash_set_sha256":
                    historical_hash_digest,

                "selected_historical_overlap":
                    0,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    cohort_manifest = {
        "schema_version":
            "BIZPROOF-V0.14-CONFIRMATORY60-COHORT-1",

        "construction_algorithm":
            "prospectively frozen before source materialization",

        "python_runtime":
            sys.version,

        "source_universe_project_count":
            6,

        "eligible_project_count":
            len(
                eligible_projects
            ),

        "selected_project_count":
            6,

        "cases_per_project":
            10,

        "case_count":
            60,

        "unique_selected_source_bodies":
            60,

        "historical_source_overlap":
            0,

        "project_distribution":
            dict(
                sorted(
                    project_distribution.items()
                )
            ),

        "stratum_distribution":
            dict(
                sorted(
                    stratum_distribution.items()
                )
            ),

        "cohort_sha256":
            cohort_sha,

        "evaluation_order_frozen":
            True,

        "bizproof_external_execution_started":
            False,

        "external_outcomes_observed":
            False,
    }

    (
        out
        / "cohort_manifest.json"
    ).write_text(
        json.dumps(
            cohort_manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "historical source hashes =",
        len(
            historical_hashes
        ),
    )

    print(
        "eligible projects        =",
        len(
            eligible_projects
        ),
    )

    print(
        "selected projects        = 6 / 6"
    )

    for index, project in enumerate(
        selected_projects,
        start=1,
    ):
        print(
            f"{index:02d}",
            project[
                "canonical_project_identity"
            ],
            project[
                "project_rank"
            ][:16],
        )

    print(
        "selected cases           = 60 / 60"
    )

    print(
        "unique source bodies     = 60 / 60"
    )

    print(
        "historical overlap       = 0"
    )

    print(
        "cohort SHA-256           =",
        cohort_sha,
    )

    print(
        "external outcomes        = NONE"
    )


if __name__ == "__main__":
    main()
