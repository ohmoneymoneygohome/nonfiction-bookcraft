#!/usr/bin/env python3
"""Check manuscript citation markers against source and citation registers."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MARKER_RE = re.compile(r"\[\^([A-Za-z0-9][A-Za-z0-9_.-]*)\]")
DEFINITION_RE = re.compile(r"^\s*\[\^([A-Za-z0-9][A-Za-z0-9_.-]*)\]:")


def safe_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes project: {relative}")
    return target


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} root must be an object")
    return value


def manuscript_markers(root: Path, manifest: dict[str, Any]) -> tuple[set[str], list[str]]:
    folder = safe_path(root, manifest.get("manuscript_dir", "MANUSCRIPT"))
    excluded = set(manifest.get("exclude", []))
    markers: set[str] = set()
    errors: list[str] = []
    if not folder.is_dir():
        return set(), [f"manuscript directory missing: {folder}"]
    for path in folder.rglob("*.md"):
        rel = path.relative_to(folder).as_posix()
        if rel in excluded:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            definition = DEFINITION_RE.match(line)
            for marker in MARKER_RE.findall(line):
                if not definition or definition.group(1) != marker:
                    markers.add(marker)
    return markers, errors


def validate(manifest_path: Path) -> tuple[dict[str, Any], list[str]]:
    root = manifest_path.resolve().parent
    manifest = load_json(manifest_path)
    errors: list[str] = []
    source_path = safe_path(root, manifest.get("source_register", "SOURCE_REGISTER.json"))
    if not source_path.is_file():
        return manifest, [f"source register missing: {source_path.name}"]
    source_register = load_json(source_path)
    sources = source_register.get("sources")
    if not isinstance(sources, list):
        errors.append("source register must contain a sources list")
        sources = []
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            errors.append("each source must have an id")
            continue
        source_id = source["id"]
        if source_id in source_ids:
            errors.append(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        for required in ("title", "type", "status"):
            if not source.get(required):
                errors.append(f"{source_id}: missing source field {required}")
        if source.get("status") == "verified" and not source.get("url_or_doi"):
            errors.append(f"{source_id}: verified source needs url_or_doi")

    citations = manifest.get("citations")
    if not isinstance(citations, list):
        errors.append("citation register must contain a citations list")
        citations = []
    citation_ids: set[str] = set()
    registered_markers: set[str] = set()
    for citation in citations:
        if not isinstance(citation, dict):
            errors.append("each citation must be an object")
            continue
        citation_id = citation.get("id")
        marker = citation.get("marker")
        if not isinstance(citation_id, str) or not isinstance(marker, str):
            errors.append("each citation needs string id and marker")
            continue
        if citation_id in citation_ids:
            errors.append(f"duplicate citation id: {citation_id}")
        citation_ids.add(citation_id)
        if not re.fullmatch(r"\[\^[A-Za-z0-9][A-Za-z0-9_.-]*\]", marker):
            errors.append(f"{citation_id}: marker must look like [^SRC-001]")
        marker_id = marker[2:-1] if marker.startswith("[^") and marker.endswith("]") else ""
        if marker_id and marker_id != citation_id:
            errors.append(f"{citation_id}: marker id must match citation id")
        registered_markers.add(marker_id or marker)
        if not citation.get("file"):
            errors.append(f"{citation_id}: missing manuscript file")
        if not citation.get("locator"):
            errors.append(f"{citation_id}: missing locator (page/section/paragraph/URL fragment)")
        source_refs = citation.get("source_ids")
        if not isinstance(source_refs, list) or not source_refs:
            errors.append(f"{citation_id}: source_ids must be a non-empty list")
        else:
            for source_id in source_refs:
                if source_id not in source_ids:
                    errors.append(f"{citation_id}: unknown source {source_id}")
                else:
                    source = next(s for s in sources if s.get("id") == source_id)
                    if source.get("status") != "verified":
                        errors.append(f"{citation_id}: source {source_id} is not verified")
        if citation.get("status", "verified") != "verified":
            errors.append(f"{citation_id}: citation status is not verified")

    markers, marker_errors = manuscript_markers(root, manifest)
    errors.extend(marker_errors)
    for marker in sorted(markers - registered_markers):
        errors.append(f"undefined manuscript citation marker: [^{marker}]")
    for marker in sorted(registered_markers - markers):
        errors.append(f"registered citation marker not found in manuscript: [^{marker}]")
    if manifest.get("require_any", True) and not markers:
        errors.append("no citation markers found; release gate requires at least one")
    return manifest, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to CITATION_REGISTER.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        manifest, errors = validate(args.manifest)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    result = {"passed": not errors, "errors": errors, "citation_count": len(manifest.get("citations", []))}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(f"ERROR {error}")
        print(f"citations={result['citation_count']} passed={result['passed']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
