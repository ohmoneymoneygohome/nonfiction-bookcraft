#!/usr/bin/env python3
"""Check figure registrations, source bindings, and reproducible assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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


def validate(manifest_path: Path) -> tuple[dict[str, Any], list[str]]:
    root = manifest_path.resolve().parent
    manifest = load_json(manifest_path)
    errors: list[str] = []
    source_register = safe_path(root, manifest.get("source_register", "SOURCE_REGISTER.json"))
    if not source_register.is_file():
        return manifest, [f"source register missing: {source_register.name}"]
    source_status = {
        entry.get("id"): entry.get("status")
        for entry in load_json(source_register).get("sources", [])
        if isinstance(entry, dict)
    }
    source_ids = set(source_status)
    figures = manifest.get("figures")
    if not isinstance(figures, list):
        return manifest, ["figure register must contain a figures list"]
    seen: set[str] = set()
    for figure in figures:
        if not isinstance(figure, dict):
            errors.append("each figure must be an object")
            continue
        figure_id = figure.get("id")
        if not isinstance(figure_id, str):
            errors.append("each figure needs an id")
            continue
        if figure_id in seen:
            errors.append(f"duplicate figure id: {figure_id}")
        seen.add(figure_id)
        for field in ("title", "file", "data_file", "generator", "source_ids", "placement", "alt_text"):
            if not figure.get(field):
                errors.append(f"{figure_id}: missing {field}")
        for field in ("file", "data_file", "generator"):
            if figure.get(field):
                try:
                    path = safe_path(root, figure[field])
                except ValueError as exc:
                    errors.append(str(exc))
                else:
                    if not path.is_file():
                        errors.append(f"{figure_id}: missing asset {figure[field]}")
        if figure.get("file") and Path(figure["file"]).suffix.lower() not in {".svg", ".png", ".jpg", ".jpeg", ".pdf"}:
            errors.append(f"{figure_id}: PDF-ready asset should be SVG, PNG, JPG, or PDF")
        source_refs = figure.get("source_ids")
        if not isinstance(source_refs, list) or not source_refs:
            errors.append(f"{figure_id}: source_ids must be a non-empty list")
        else:
            for source_id in source_refs:
                if source_id not in source_ids:
                    errors.append(f"{figure_id}: unknown source {source_id}")
                elif source_status[source_id] != "verified":
                    errors.append(f"{figure_id}: source {source_id} is not verified")
        if figure.get("generator_type") == "echarts" and Path(str(figure.get("generator", ""))).suffix.lower() not in {".js", ".mjs", ".ts"}:
            errors.append(f"{figure_id}: ECharts generator should be a JS/MJS/TS file")
    return manifest, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to FIGURE_REGISTER.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        manifest, errors = validate(args.manifest)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    result = {"passed": not errors, "errors": errors, "figure_count": len(manifest.get("figures", []))}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(f"ERROR {error}")
        print(f"figures={result['figure_count']} passed={result['passed']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
