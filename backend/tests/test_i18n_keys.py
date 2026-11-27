"""Every translation key referenced by code must exist in both locale files.

`t()` in the frontend falls back to returning the raw key, so a missing key
shows users text like "errors.internal". Backend `message_key`s are rendered
by the frontend through the same dictionaries.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO / "backend" / "app"
FRONTEND_APP = REPO / "frontend" / "app"
LOCALES = {
    "fr": FRONTEND_APP / "locales" / "fr.ts",
    "ar": FRONTEND_APP / "locales" / "ar.ts",
}

_KEY_RE = re.compile(r"^\s*([A-Za-z_]\w*|\"[^\"]+\"|'[^']+')\s*:\s*(.*?)\s*$")
_BACKEND_KEY_RES = [
    re.compile(r"""message_key\s*=\s*["']([a-z_][\w.]*)["']"""),
    re.compile(r"""["'](errors\.[a-z_][\w.]*)["']"""),
]
_FRONTEND_T_RE = re.compile(r"""\bt\(\s*(["'])([a-z_][\w]*(?:\.[\w]+)+)\1\s*[,)]""")


def parse_locale_keys(path: Path) -> set[str]:
    """Flatten a `export default { a: { b: "..." } }` TS dictionary into dotted keys."""
    keys: set[str] = set()
    stack: list[str] = []
    depth = 0  # brace depth inside `export default {`
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("//", 1)[0] if raw.lstrip().startswith("//") else raw
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("export default"):
            depth = 1
            continue
        m = _KEY_RE.match(line)
        if m and depth >= 1:
            name = m.group(1).strip("\"'")
            rest = m.group(2)
            if rest.startswith("{") and not rest.rstrip(",").endswith("}"):
                stack.append(name)
                depth += 1
            else:
                keys.add(".".join([*stack, name]))
            continue
        if stripped.startswith("}"):
            depth -= 1
            if stack:
                stack.pop()
    assert keys, f"no keys parsed from {path}"
    return keys


def _scan(root: Path, patterns: tuple[str, ...], regexes, group: int) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for pattern in patterns:
        for f in root.rglob(pattern):
            if "node_modules" in f.parts or ".nuxt" in f.parts or ".output" in f.parts:
                continue
            if f.parent.name == "locales":
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            for rx in regexes:
                for m in rx.finditer(text):
                    found.setdefault(m.group(group), set()).add(str(f.relative_to(REPO)))
    return found


def backend_keys() -> dict[str, set[str]]:
    return _scan(BACKEND_APP, ("*.py",), _BACKEND_KEY_RES, 1)


def frontend_keys() -> dict[str, set[str]]:
    return _scan(FRONTEND_APP, ("*.vue", "*.ts"), [_FRONTEND_T_RE], 2)


def test_locale_parser_sees_nested_keys():
    fr = parse_locale_keys(LOCALES["fr"])
    assert "common.save" in fr
    assert "errors.generic" in fr


def test_scanners_find_references():
    assert "errors.patient_not_found" in backend_keys()
    assert "common.save" in frontend_keys()


@pytest.mark.parametrize("lang", sorted(LOCALES))
def test_every_referenced_key_exists(lang):
    available = parse_locale_keys(LOCALES[lang])
    used = {**frontend_keys(), **backend_keys()}
    missing = {k: sorted(v) for k, v in sorted(used.items()) if k not in available}
    assert not missing, f"keys missing from {lang}.ts: " + "; ".join(
        f"{k} (used in {', '.join(v)})" for k, v in missing.items()
    )


def test_locales_have_same_keys():
    fr = parse_locale_keys(LOCALES["fr"])
    ar = parse_locale_keys(LOCALES["ar"])
    assert fr - ar == set(), f"in fr.ts only: {sorted(fr - ar)}"
    assert ar - fr == set(), f"in ar.ts only: {sorted(ar - fr)}"
