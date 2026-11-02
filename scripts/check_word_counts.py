#!/usr/bin/env python3
"""Enforce per-chapter word-count thresholds for Chinese nonfiction manuscripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


COUNT_MODE = "han_char_plus_ascii_word"
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*")
FENCED_CODE_RE = re.compile(r"(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$")
HTML_COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"</?[^>]+>")


@dataclass
class ChapterResult:
    file: str
    actual_words: int
    min_words: int
    max_words: int | None
    status: str


def visible_markdown(text: str) -> str:
    """Keep visible prose while removing markup and non-prose code/URLs."""
    if text.startswith("---\n") or text.startswith("---\r\n"):
        lines = text.splitlines()
        try:
            end = lines.index("---", 1)
            text = "\n".join(lines[end + 1 :])
        except ValueError:
            pass
    text = FENCED_CODE_RE.sub(" ", text)
    text = HTML_COMMENT_RE.sub(" ", text)
    text = IMAGE_RE.sub(" ", text)
    text = LINK_RE.sub(r"\1", text)
    text = URL_RE.sub(" ", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s{0,3}>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+", "", text)
    return text


def count_words(text: str) -> int:
    visible = visible_markdown(text)
    han = sum(
        1
        for char in visible
        if unicodedata.name(char, "").startswith(
            ("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-")
        )
    )
    ascii_words = len(ASCII_WORD_RE.findall(visible))
    return han + ascii_words


def classify_count(actual: int, min_words: int, max_words: int | None = None) -> str:
    if actual < min_words:
        return "SHORT"
    if max_words is not None and actual > max_words:
        return "OVER"
    return "PASS"


def read_manifest(path: Path) -> tuple[dict[str, Any], Path]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    if data.get("count_mode", COUNT_MODE) != COUNT_MODE:
        raise ValueError(f"count_mode must be {COUNT_MODE!r}")
    if not isinstance(data.get("manuscript_dir"), str):
        raise ValueError("manifest must define manuscript_dir")
    if not isinstance(data.get("chapters"), list) or not data["chapters"]:
        raise ValueError("manifest must define a non-empty chapters list")
    root = path.resolve().parent
    manuscript_dir = (root / data["manuscript_dir"]).resolve()
    if not manuscript_dir.is_relative_to(root):
        raise ValueError("manuscript_dir must remain inside the project directory")
    return data, root


def _safe_child(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes project directory: {relative}")
    return target


def validate(data: dict[str, Any], root: Path) -> tuple[list[ChapterResult], list[str]]:
    errors: list[str] = []
    results: list[ChapterResult] = []
    manuscript_dir = _safe_child(root, data["manuscript_dir"])
    if not manuscript_dir.is_dir():
        return [], [f"manuscript directory does not exist: {data['manuscript_dir']}"]

    excluded = set(data.get("exclude", []))
    listed: dict[str, dict[str, Any]] = {}
    for entry in data["chapters"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            errors.append("each chapter entry must contain a file path")
            continue
        name = entry["file"].replace("\\", "/")
        if name in listed:
            errors.append(f"duplicate chapter entry: {name}")
            continue
        low = entry.get("min_words")
        high = entry.get("max_words")
        if not isinstance(low, int) or isinstance(low, bool) or low < 1:
            errors.append(f"{name}: min_words must be a positive integer")
            continue
        if high is not None and (not isinstance(high, int) or isinstance(high, bool) or high < low):
            errors.append(f"{name}: max_words must be an integer >= min_words")
            continue
        listed[name] = {**entry, "file": name}

    for rel, entry in listed.items():
        try:
            file_path = _safe_child(manuscript_dir, rel)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not file_path.is_file():
            errors.append(f"listed chapter missing: {rel}")
            continue
        actual = count_words(file_path.read_text(encoding="utf-8"))
        low = entry["min_words"]
        high = entry.get("max_words")
        status = classify_count(actual, low, high)
        results.append(ChapterResult(rel, actual, low, high, status))

    expected = {
        p.relative_to(manuscript_dir).as_posix()
        for p in manuscript_dir.rglob("*.md")
        if p.is_file()
    }
    accounted = set(listed) | {str(p).replace("\\", "/") for p in excluded}
    for missing in sorted(expected - accounted):
        errors.append(f"unaccounted manuscript file (add chapter or exclude): {missing}")
    for extra in sorted(accounted - expected):
        errors.append(f"listed/excluded file not found in manuscript directory: {extra}")

    outline_path = data.get("outline_path")
    if outline_path:
        try:
            outline_file = _safe_child(root, outline_path)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if not outline_file.is_file():
                errors.append(f"outline file missing: {outline_path}")
            else:
                outline_text = outline_file.read_text(encoding="utf-8")
                outline_targets = [
                    int(value.replace(",", ""))
                    for value in re.findall(r"目标字数\s*[:：]\s*([\d,]+)", outline_text)
                ]
                manifest_targets = [entry["min_words"] for entry in listed.values()]
                if outline_targets != manifest_targets:
                    errors.append(
                        "outline target sequence does not match chapter min_words "
                        f"(outline={outline_targets}, manifest={manifest_targets})"
                    )

    return results, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to WORD_COUNT_TARGETS.json")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--report", type=Path, help="also write the report as JSON")
    args = parser.parse_args()

    try:
        data, root = read_manifest(args.manifest.resolve())
        results, errors = validate(data, root)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    failed = any(result.status != "PASS" for result in results)
    report = {
        "count_mode": COUNT_MODE,
        "passed": not errors and not failed,
        "chapters": [asdict(result) for result in results],
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for result in results:
            target = f">={result.min_words}"
            if result.max_words is not None:
                target += f"<={result.max_words}"
            print(f"{result.status:5} {result.actual_words:>7} / {target:<14} {result.file}")
        for error in errors:
            print(f"ERROR {error}")
        passed = sum(result.status == "PASS" for result in results)
        print(f"\n{passed}/{len(results)} chapters pass; {len(errors)} manifest error(s).")

    if errors:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
