"""Validate an OKF 0.2 bundle directory against the llm-wiki contract.

This module locks down the OKF 0.2 frontmatter contract as code. ``validate_bundle``
is the source of truth for what makes a bundle conformant; later stages (content
migration, CLI wiring) consume its output.

Schema overview
---------------
Bundle root ``index.md`` frontmatter (REQUIRED)::

    okf_version: "0.2"

Concept files frontmatter:

* REQUIRED: ``type`` — non-empty string.
* RECOMMENDED: ``title``, ``description``, ``tags`` (list of strings).
* OPTIONAL (OKF 0.2):

    ``generated``            mapping ``{by: <string>, at: <string>}`` — last-change
                             attribution.
    ``sources``              list; each entry is either a bare string or a mapping
                             with ``resource`` and/or ``last_modified`` (credibility
                             signals live on each entry).
    ``verified``             list; each entry is a mapping ``{by: <string>, at: <string>}``.
    ``status``               one of ``draft``, ``stable``, ``deprecated``.
    ``resource``             primary external resource (string).
    ``usage_window``         mapping describing temporal validity (shape is
                             tool-defined — only ``mapping`` is enforced here).
    ``attested_computation`` mapping for provenance of derived fields; shape is
                             tool-defined — only ``mapping`` is enforced here.

Bundle layout rules (post-migration shape):

* The bundle root contains ``index.md`` (with ``okf_version: "0.2"``) and
  ``log.md``.
* Concept subdirs (``summaries/``, ``concepts/``, ``entities/``,
  ``insights/``) sit directly at the bundle root — NOT under ``wiki/``.
* Reserved filenames (``index.md``, ``log.md``) are only legal at the
  bundle root and must not appear inside concept subdirs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# OKF version this validator enforces. Must match the bundle root
# ``index.md`` frontmatter ``okf_version`` field.
OKF_VERSION: str = "0.2"

# Filenames reserved for bundle-level metadata. Only legal at the bundle
# root; forbidden inside concept subdirs.
RESERVED_FILES: frozenset[str] = frozenset({"index.md", "log.md"})

# llm-wiki concept subdirs (post-migration OKF bundle shape).
CONCEPT_SUBDIRS: frozenset[str] = frozenset(
    {"summaries", "concepts", "entities", "insights"}
)

# Allowed values for the frontmatter ``status`` field.
ALLOWED_STATUS: frozenset[str] = frozenset({"draft", "stable", "deprecated"})


@dataclass(frozen=True)
class Violation:
    """A rule violation reported by :func:`validate_bundle`.

    Attributes:
        path:    Bundle-relative POSIX path to the offending file, or ``""``
                 for whole-bundle rules (e.g. missing root ``index.md``).
        rule:    Stable machine-readable identifier (e.g. ``type_missing``).
        message: Human-readable explanation of the violation.
    """

    path: str
    rule: str
    message: str


def _read_frontmatter(path: Path) -> tuple[dict, str | None]:
    """Read ``path`` and split it into ``(frontmatter_dict, body)``.

    Returns ``(frontmatter, body)`` on success. ``frontmatter`` is the parsed
    YAML mapping and ``body`` is the markdown body with the leading blank
    line stripped. Returns ``({}, None)`` on failure (no ``---`` block, bad
    YAML, or root that isn't a mapping).
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, None
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, None
    fm_text = text[4:end]
    try:
        loaded = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return {}, None
    if not isinstance(loaded, dict):
        return {}, None
    body = text[end + 5 :]
    body = body.removeprefix("\n")
    return loaded, body


def _frontmatter_status(path: Path) -> str:
    """Return the parse status of ``path``'s frontmatter.

    ``"ok"``         — parseable YAML mapping.
    ``"missing"``    — no ``---``-delimited block.
    ``"unparseable"``— block present but YAML error or root not a mapping.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return "missing"
    end = text.find("\n---\n", 4)
    if end == -1:
        return "unparseable"
    fm_text = text[4:end]
    try:
        loaded = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return "unparseable"
    if not isinstance(loaded, dict):
        return "unparseable"
    return "ok"


def _check_concept_frontmatter(rel: str, fm: dict) -> list[Violation]:
    """Run per-concept-field rules against a parsed frontmatter dict."""
    out: list[Violation] = []

    # type — required, non-empty string.
    t = fm.get("type")
    if t is None:
        out.append(
            Violation(
                rel,
                "type_missing",
                "frontmatter is missing required 'type' field",
            )
        )
    elif not isinstance(t, str) or not t.strip():
        out.append(
            Violation(
                rel,
                "type_empty",
                "frontmatter 'type' must be a non-empty string",
            )
        )

    # generated — when present, must be a mapping with string 'by' and 'at'.
    g = fm.get("generated")
    if g is not None:
        if not isinstance(g, dict) or not (
            isinstance(g.get("by"), str) and isinstance(g.get("at"), str)
        ):
            out.append(
                Violation(
                    rel,
                    "generated_malformed",
                    "'generated' must be a mapping with string 'by' and 'at'",
                )
            )

    # sources — when present, list whose entries are mappings (with 'resource'
    # and/or 'last_modified') or bare strings.
    s = fm.get("sources")
    if s is not None:
        if not isinstance(s, list):
            out.append(
                Violation(
                    rel,
                    "sources_malformed",
                    "'sources' must be a list of mappings or strings",
                )
            )
        else:
            for i, entry in enumerate(s):
                if isinstance(entry, str):
                    continue
                if not isinstance(entry, dict):
                    out.append(
                        Violation(
                            rel,
                            "sources_malformed",
                            f"sources[{i}] must be a mapping or string",
                        )
                    )
                    continue
                if "resource" not in entry and "last_modified" not in entry:
                    out.append(
                        Violation(
                            rel,
                            "sources_malformed",
                            (
                                f"sources[{i}] must declare 'resource' "
                                "and/or 'last_modified'"
                            ),
                        )
                    )

    # verified — when present, list whose entries are {by, at} mappings.
    v = fm.get("verified")
    if v is not None:
        if not isinstance(v, list):
            out.append(
                Violation(
                    rel,
                    "verified_malformed",
                    "'verified' must be a list of {by, at} mappings",
                )
            )
        else:
            for i, entry in enumerate(v):
                if not isinstance(entry, dict) or not (
                    isinstance(entry.get("by"), str)
                    and isinstance(entry.get("at"), str)
                ):
                    out.append(
                        Violation(
                            rel,
                            "verified_malformed",
                            (
                                f"verified[{i}] must be a mapping with "
                                "string 'by' and 'at'"
                            ),
                        )
                    )

    # status — when present, one of draft | stable | deprecated.
    status = fm.get("status")
    if status is not None and status not in ALLOWED_STATUS:
        out.append(
            Violation(
                rel,
                "status_invalid",
                (
                    f"'status' must be one of {sorted(ALLOWED_STATUS)} "
                    f"(got {status!r})"
                ),
            )
        )

    return out


def validate_bundle(bundle_dir: str | Path) -> list[Violation]:
    """Validate ``bundle_dir`` as an OKF 0.2 bundle.

    Returns the list of rule violations. An empty list means the bundle
    conforms. The function never raises; missing files produce violations
    rather than exceptions.

    ``bundle_dir`` is resolved before walking. Symlinks are followed the
    same way :func:`Path.rglob` follows them — reserved-name and
    layout rules apply to the resolved path.
    """
    bundle_dir = Path(bundle_dir).resolve()
    violations: list[Violation] = []

    if not bundle_dir.is_dir():
        return [
            Violation(
                "",
                "bundle_not_found",
                f"bundle directory not found: {bundle_dir}",
            )
        ]

    # Bundle root ``index.md`` — must declare ``okf_version: "0.2"``.
    root_index = bundle_dir / "index.md"
    if not root_index.is_file():
        violations.append(
            Violation(
                "",
                "okf_version_missing",
                "bundle root index.md is required and must declare okf_version",
            )
        )
    else:
        fm, _ = _read_frontmatter(root_index)
        v = fm.get("okf_version")
        if v is None:
            violations.append(
                Violation(
                    "index.md",
                    "okf_version_missing",
                    "root index.md frontmatter is missing 'okf_version'",
                )
            )
        elif v != OKF_VERSION:
            violations.append(
                Violation(
                    "index.md",
                    "okf_version_wrong",
                    (
                        f"root index.md okf_version must be {OKF_VERSION!r} "
                        f"(got {v!r})"
                    ),
                )
            )

    # Walk every ``.md`` file in the bundle and enforce per-file rules.
    for md in sorted(bundle_dir.rglob("*.md")):
        rel = md.relative_to(bundle_dir).as_posix()
        parts = rel.split("/")
        top = parts[0]

        # Post-migration shape: concept files must NOT live under ``wiki/``.
        if top == "wiki":
            violations.append(
                Violation(
                    rel,
                    "wiki_layout_pre_migration",
                    (
                        "concept files must not be inside wiki/ "
                        "(post-migration OKF bundle shape)"
                    ),
                )
            )
            continue

        # Root-level reserved files: ``index.md`` already validated above;
        # ``log.md`` is a pass-through with no schema.
        if rel == "index.md":
            continue
        if rel == "log.md":
            continue

        # Reserved filenames inside concept subdirs are forbidden.
        if top in CONCEPT_SUBDIRS and md.name in RESERVED_FILES:
            violations.append(
                Violation(
                    rel,
                    "reserved_filename_in_subdir",
                    (
                        f"reserved filename {md.name!r} must not appear "
                        f"inside {top}/"
                    ),
                )
            )
            continue

        # Concept file — frontmatter must be parseable and well-shaped.
        status = _frontmatter_status(md)
        if status != "ok":
            violations.append(
                Violation(
                    rel,
                    "no_frontmatter",
                    f"file has {status} YAML frontmatter",
                )
            )
            continue
        fm, _ = _read_frontmatter(md)
        violations.extend(_check_concept_frontmatter(rel, fm))

    return violations