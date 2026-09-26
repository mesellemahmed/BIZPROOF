#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCES_JSON="$ROOT_DIR/benchmarks/v0.6/sources.json"
LOCK_JSON="$ROOT_DIR/benchmarks/v0.6/LOCK.json"
EXTERNAL_ROOT="$ROOT_DIR/external_sources/v0.6"

mkdir -p "$EXTERNAL_ROOT"

if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is required."
    exit 1
fi

if ! command -v python >/dev/null 2>&1; then
    echo "ERROR: python is required."
    exit 1
fi


echo "===== V0.6 EXTERNAL ACQUISITION ====="


mapfile -t SOURCE_ROWS < <(
python - "$SOURCES_JSON" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(
    Path(sys.argv[1]).read_text(encoding="utf-8")
)

for source in payload["sources"]:

    roots = []

    for key in ("code_roots", "test_roots", "doc_roots"):
        for root in source.get(key, []):
            # Cone-mode sparse checkout automatically includes
            # top-level files such as README.md.
            suffix = Path(root).suffix.lower()

            if suffix in {".md", ".rst", ".txt"}:
                continue

            if root not in roots:
                roots.append(root)

    print(
        "\t".join(
            [
                source["id"],
                source["repository"],
                source["ref"],
                "|".join(roots),
            ]
        )
    )
PY
)


if [ "${#SOURCE_ROWS[@]}" -eq 0 ]; then
    echo "ERROR: no external sources configured."
    exit 1
fi


for row in "${SOURCE_ROWS[@]}"; do

    IFS=$'\t' read -r \
        source_id \
        repository \
        requested_ref \
        sparse_roots_raw \
        <<< "$row"

    # Git Bash on Windows may preserve CR from Python stdout.
    source_id="${source_id//$'\r'/}"
    repository="${repository//$'\r'/}"
    requested_ref="${requested_ref//$'\r'/}"
    sparse_roots_raw="${sparse_roots_raw//$'\r'/}"

    target="$EXTERNAL_ROOT/$source_id"


    echo ""
    echo "===== SOURCE: $source_id ====="
    echo "Repository : $repository"
    echo "Ref        : $requested_ref"


    # Always rebuild external working copies from scratch.
    # They are untracked and reproducible from LOCK.json.
    rm -rf "$target"


    echo "Sparse cloning..."

    git clone \
        --depth 1 \
        --filter=blob:none \
        --no-checkout \
        --branch "$requested_ref" \
        "$repository" \
        "$target" || exit 1


    # Additional protection for Git for Windows.
    git -C "$target" config core.longpaths true || exit 1


    echo "Initializing sparse checkout..."

    git -C "$target" sparse-checkout init --cone || exit 1


    IFS='|' read -r -a sparse_roots <<< "$sparse_roots_raw"

    echo "Sparse roots:"

    for root in "${sparse_roots[@]}"; do
        if [ -n "$root" ]; then
            echo "  - $root"
        fi
    done


    if [ "${#sparse_roots[@]}" -gt 0 ]; then

        git -C "$target" \
            sparse-checkout set \
            "${sparse_roots[@]}" \
            || exit 1

    fi


    echo "Materializing working tree..."

    git -C "$target" checkout --detach HEAD || exit 1


    resolved_commit="$(
        git -C "$target" rev-parse HEAD
    )"

    echo "Commit: $resolved_commit"


    echo "Working-tree root contents:"

    find "$target" \
        -mindepth 1 \
        -maxdepth 2 \
        -not -path '*/.git/*' \
        -not -path '*/.git' \
        | head -40

done


echo ""
echo "===== WRITE LOCK FILE ====="


python - "$SOURCES_JSON" "$LOCK_JSON" "$EXTERNAL_ROOT" <<'PY'
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import sys

from pathlib import Path
from typing import Any


sources_path = Path(sys.argv[1])
lock_path = Path(sys.argv[2])
external_root = Path(sys.argv[3])


payload: dict[str, Any] = json.loads(
    sources_path.read_text(encoding="utf-8")
)


locked: list[dict[str, Any]] = []


for source in payload["sources"]:

    source_id = str(source["id"])
    repo = external_root / source_id


    def git(*args: str) -> str:

        return subprocess.check_output(
            [
                "git",
                "-C",
                str(repo),
                *args,
            ],
            text=True,
        ).strip()


    license_candidates = [
        repo / "LICENSE",
        repo / "LICENSE.txt",
        repo / "LICENSE.rst",
        repo / "LICENSE.md",
        repo / "LICENSE.AGPL.txt",
        repo / "COPYING",
        repo / "COPYING.txt",
    ]


    license_path = next(
        (
            candidate
            for candidate in license_candidates
            if candidate.exists()
        ),
        None,
    )


    license_sha256 = None
    relative_license = None


    if license_path is not None:

        license_sha256 = hashlib.sha256(
            license_path.read_bytes()
        ).hexdigest()

        relative_license = str(
            license_path.relative_to(repo)
        )


    sparse_roots: list[str] = []

    for key in (
        "code_roots",
        "test_roots",
        "doc_roots",
    ):

        for root in source.get(key, []):

            if root not in sparse_roots:
                sparse_roots.append(root)


    locked.append(
        {
            "id": source_id,
            "repository": source["repository"],
            "requested_ref": source["ref"],
            "resolved_commit": git(
                "rev-parse",
                "HEAD",
            ),
            "commit_date": git(
                "show",
                "-s",
                "--format=%cI",
                "HEAD",
            ),
            "describe": git(
                "describe",
                "--tags",
                "--always",
            ),
            "license_declared": source["license"],
            "license_file": relative_license,
            "license_sha256": license_sha256,
            "sparse_checkout": True,
            "materialized_roots": sparse_roots,
        }
    )


lock = {
    "corpus_version": "0.6.0",
    "generated_at_utc": (
        dt.datetime.now(dt.UTC).isoformat()
    ),
    "acquisition_mode": (
        "shallow-filtered-sparse-checkout"
    ),
    "sources": locked,
}


lock_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)


lock_path.write_text(
    json.dumps(
        lock,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print()
print(
    f"Lock written: {lock_path}"
)

PY


echo ""
echo "===== V0.6 ACQUISITION COMPLETE ====="

