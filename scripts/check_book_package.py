#!/usr/bin/env python3
"""Validate the production elements and technical integrity of a book PDF."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BASE14 = {"/Helvetica", "/Helvetica-Bold", "/Times-Roman", "/Times-Bold", "/Courier", "/Symbol", "/ZapfDingbats"}


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
    if manifest.get("status", "release") != "release":
        errors.append(f"package status is {manifest.get('status')!r}; release requires 'release'")
    for field in ("pdf", "cover", "title_page", "copyright_page", "toc", "references"):
        if not manifest.get(field):
            errors.append(f"package manifest missing {field}")
        else:
            path = safe_path(root, manifest[field])
            if not path.is_file():
                errors.append(f"missing package asset {manifest[field]}")
    for field in ("citation_register", "figure_register"):
        if manifest.get(field):
            path = safe_path(root, manifest[field])
            if not path.is_file():
                errors.append(f"missing register {manifest[field]}")
    for field in ("chapter_files", "required_text"):
        if not isinstance(manifest.get(field), list) or not manifest[field]:
            errors.append(f"package manifest needs non-empty {field}")
    pdf_path = safe_path(root, manifest["pdf"]) if manifest.get("pdf") else None
    if pdf_path and pdf_path.is_file():
        try:
            from pypdf import PdfReader
        except ImportError:
            errors.append("pypdf is required for PDF package validation")
        else:
            try:
                reader = PdfReader(str(pdf_path))
                if len(reader.pages) < int(manifest.get("page_count_min", 1)):
                    errors.append(f"PDF has {len(reader.pages)} pages, below page_count_min")
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                for required in manifest.get("required_text", []):
                    if required not in text:
                        errors.append(f"required text not found in PDF: {required}")
                embedded_fonts: set[str] = set()
                for page in reader.pages:
                    for ref in page.get("/Resources", {}).get("/Font", {}).values():
                        font = ref.get_object()
                        name = str(font.get("/BaseFont"))
                        descriptor = font.get("/FontDescriptor")
                        if descriptor and any(descriptor.get(key) for key in ("/FontFile", "/FontFile2", "/FontFile3")):
                            embedded_fonts.add(name)
                        elif name not in BASE14:
                            errors.append(f"font is not embedded: {name}")
                if manifest.get("require_embedded_font", True) and not embedded_fonts:
                    errors.append("no embedded font found in PDF")
                metadata = reader.metadata or {}
                if manifest.get("require_title_metadata", True) and not metadata.get("/Title"):
                    errors.append("PDF metadata has no /Title")
            except Exception as exc:
                errors.append(f"cannot parse PDF: {exc}")
    for chapter in manifest.get("chapter_files", []):
        path = safe_path(root, chapter)
        if not path.is_file():
            errors.append(f"chapter source missing: {chapter}")
    return manifest, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to BOOK_PACKAGE.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        manifest, errors = validate(args.manifest)
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    result = {"passed": not errors, "errors": errors, "pdf": manifest.get("pdf")}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for error in errors:
            print(f"ERROR {error}")
        print(f"pdf={result['pdf']} passed={result['passed']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
