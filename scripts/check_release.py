#!/usr/bin/env python3
"""Run the word-count, citation, figure, and PDF package release gates together."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_book_package import validate as validate_package
from check_citations import validate as validate_citations
from check_figures import validate as validate_figures
from check_word_counts import read_manifest as read_word_manifest, validate as validate_words


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.project.resolve()
    checks: dict[str, dict] = {}

    word_manifest = root / "WORD_COUNT_TARGETS.json"
    try:
        data, manifest_root = read_word_manifest(word_manifest)
        results, errors = validate_words(data, manifest_root)
        checks["word_count"] = {
            "passed": not errors and all(item.status == "PASS" for item in results),
            "errors": errors,
            "chapters": [item.__dict__ for item in results],
        }
    except Exception as exc:
        checks["word_count"] = {"passed": False, "errors": [str(exc)]}

    for name, filename, validator in (
        ("citations", "CITATION_REGISTER.json", validate_citations),
        ("figures", "FIGURE_REGISTER.json", validate_figures),
        ("book_package", "BOOK_PACKAGE.json", validate_package),
    ):
        path = root / filename
        try:
            manifest, errors = validator(path)
            checks[name] = {"passed": not errors, "errors": errors}
        except Exception as exc:
            checks[name] = {"passed": False, "errors": [str(exc)]}

    passed = all(result.get("passed") for result in checks.values())
    output = {"passed": passed, "checks": checks}
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        for name, result in checks.items():
            print(f"{name}: {'PASS' if result['passed'] else 'FAIL'}")
            for error in result.get("errors", []):
                print(f"  ERROR {error}")
        print(f"release_gate={'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
