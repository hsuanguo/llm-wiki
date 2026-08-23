"""OKF conformance validator.

This module is the canonical reference for what an OKF-native bundle must
look like on disk. It is consumed by:

- ``lwiki init`` (stage 2) — to confirm the scaffold is conformant.
- ``lwiki serve`` (stage 4) — to surface warnings on startup, and to
  reject legacy frontmatter on page writes.
- ``lwiki validate`` / ``lwiki export okf`` (stage 7) — the CLI shape.
- ``lwiki migrate`` (stage 6) — to verify a converted bundle.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

The rules below are deliberately stricter than the spec's conformance
floor (the spec says "consumers MUST NOT reject bundles for unknown keys"
etc.). We are a producer and authoring tool: stricter checks catch
mistakes early. Each violation is tagged with a ``level`` so we can
report informational findings vs. errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from .okf_export import OKF_VERSION, parse_frontmatter

# Concept subdirectories that the on-disk shape recognises. OKF does not
# require any specific hierarchy; llm-wiki keeps these four for tooling.
WIKI_SUBDIRS: tuple[str, ...] = ("summaries", "concepts", "entities", "insights")

# Reserved filenames. Per the OKF spec, ``index.md`` and ``log.md`` are
# reserved at the bundle root and must not appear elsewhere.
RESERVED = frozenset({"index.md", "log.md"})

# Recognised ``type`` values. Producers MAY use unknown values; consumers
# MUST tolerate them. We surface unknown values as ``Level.INFO`` rather
# than ``Level.ERROR``.
KNOWN_TYPES: frozenset[str] = frozenset(
    {
        "summary",
        "concept",
        "entity",
        "insight",
        "overview",
        "attested-computation",
    }
)

# Allowed values for the optional ``status`` frontmatter field.
KNOWN_STATUS: frozenset[str] = frozenset({"draft", "stable", "deprecated"})


class Level(str, Enum):
    """Severity of a conformance violation."""

    ERROR = "error"  # bundle is not a valid OKF bundle
    WARN = "warn"  # strongly recommended field missing or malformed
    INFO = "info"  # notable but not a defect


@dataclass(frozen=True)
class Violation:
    """A single conformance finding.

    ``path`` is bundle-relative for concept violations; ``None`` for
    bundle-wide checks (e.g. missing root ``okf_version``).
    """

    level: Level
    code: str
    message: str
    path: str | None = None


# ---------------------------------------------------------------------------
# Public API.


def validate_bundle(bundle_dir: Path | str) -> list[Violation]:
    """Walk ``bundle_dir`` and return every conformance finding.

    Empty bundles (just ``index.md`` with ``okf_version``) pass with no
    violations. A bundle that does not exist returns one ERROR.
    """
    bundle_dir = Path(bundle_dir).resolve()
    if not bundle_dir.is_dir():
        return [
            Violation(
                Level.ERROR,
                "bundle.missing",
                f"bundle directory not found: {bundle_dir}",
            )
        ]

    out: list[Violation] = []
    out.extend(_check_root_index(bundle_dir))
    out.extend(_check_no_legacy_wiki_wrapper(bundle_dir))
    out.extend(_check_concept_files(bundle_dir))
    return out


def is_conformant(violations: Iterable[Violation]) -> bool:
    """A bundle is conformant iff there are no ERROR-level findings."""
    return not any(v.level == Level.ERROR for v in violations)


# ---------------------------------------------------------------------------
# Rule implementations.


def _check_root_index(bundle_dir: Path) -> list[Violation]:
    root_index = bundle_dir / "index.md"
    if not root_index.is_file():
        return [
            Violation(
                Level.ERROR,
                "root.index_missing",
                "bundle root must contain index.md (OKF spec §8)",
            )
        ]
    text = root_index.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(text)
    version = fm.get("okf_version")
    if not version:
        return [
            Violation(
                Level.ERROR,
                "root.okf_version_missing",
                "bundle root index.md must declare okf_version in its frontmatter",
            )
        ]
    if str(version).strip('"').strip("'") != OKF_VERSION:
        return [
            Violation(
                Level.WARN,
                "root.okf_version_wrong",
                f"okf_version is {version!r}, expected {OKF_VERSION!r}",
            )
        ]
    return []


def _check_no_legacy_wiki_wrapper(bundle_dir: Path) -> list[Violation]:
    """Reject the pre-migration shape: concept files inside a ``wiki/`` subdir."""
    legacy = bundle_dir / "wiki"
    if not legacy.is_dir():
        return []
    # If wiki/ exists but has no concept subdirs, treat it as inert (legacy).
    if not any((legacy / sub).is_dir() for sub in WIKI_SUBDIRS):
        return []
    return [
        Violation(
            Level.ERROR,
            "legacy.wiki_wrapper",
            "bundle still uses the legacy wiki/ wrapper — concepts must live at the bundle root",
        )
    ]


def _check_concept_files(bundle_dir: Path) -> list[Violation]:
    out: list[Violation] = []
    for path in sorted(bundle_dir.rglob("*.md")):
        rel = path.relative_to(bundle_dir).as_posix()
        out.extend(_check_one_file(path, rel))
    return out


def _check_one_file(path: Path, rel: str) -> list[Violation]:
    out: list[Violation] = []

    name = path.name
    top = rel.split("/", 1)[0]
    in_subdir = top in WIKI_SUBDIRS

    # Per-directory index files (`<subdir>/index.md`) are OKF's
    # directory-listing convention. They are exempt from the reserved
    # filename rule and from concept frontmatter checks — they are
    # bullet-list directory indexes, not concepts. Frontmatter is still
    # reserved for the bundle root only per OKF spec, so a per-subdir
    # index.md that carries concept frontmatter is not flagged here, but
    # authors should keep these files frontmatter-free.
    is_directory_index = name == "index.md" and in_subdir

    # Reserved filenames are not allowed as concept files in subdirs.
    # `index.md` in a concept subdir is a directory index (handled above);
    # `log.md` in a subdir is always an error.
    if name in RESERVED and not is_directory_index and rel not in ("index.md", "log.md"):
        out.append(
            Violation(
                Level.ERROR,
                "concept.reserved_filename",
                f"reserved filename {name!r} used outside the bundle root",
                path=rel,
            )
        )

    # log.md, the root index.md, and per-directory indexes are special —
    # skip concept frontmatter shape checks for them.
    if rel in ("index.md", "log.md") or is_directory_index:
        return out

    text = path.read_text(encoding="utf-8")
    try:
        fm, _ = parse_frontmatter(text)
    except Exception as exc:  # parse_frontmatter swallows YAML errors and
        # returns an empty dict, but be defensive in case the file
        # itself is unreadable.
        out.append(
            Violation(
                Level.ERROR,
                "concept.frontmatter_unreadable",
                f"could not read frontmatter: {exc}",
                path=rel,
            )
        )
        return out

    # Bundles may include README.md, AGENTS.md, or other top-level
    # convention files; those don't need frontmatter. Concept files
    # (top-level or in subdirs) do.
    if name in {"AGENTS.md", "CLAUDE.md", "README.md"}:
        return out
    if not in_subdir and top not in {"", "overview.md"}:
        # Top-level files that aren't concept files are allowed but should
        # carry frontmatter if they're intended as concepts. Skip the type
        # requirement for these to avoid false positives.
        return out

    if not fm:
        out.append(
            Violation(
                Level.ERROR,
                "concept.frontmatter_missing",
                "concept file has no YAML frontmatter",
                path=rel,
            )
        )
        return out

    type_val = fm.get("type")
    if not type_val or not str(type_val).strip():
        out.append(
            Violation(
                Level.ERROR,
                "concept.type_missing",
                "concept frontmatter is missing the required 'type' field",
                path=rel,
            )
        )
    elif str(type_val) not in KNOWN_TYPES:
        out.append(
            Violation(
                Level.INFO,
                "concept.type_unknown",
                f"unknown type {type_val!r}; consumers will tolerate it but consider documenting it",
                path=rel,
            )
        )

    # Optional OKF fields — only validate when present.
    if "generated" in fm:
        out.extend(_check_generated(fm.get("generated"), rel))
    if "sources" in fm:
        out.extend(_check_sources(fm.get("sources"), rel))
    if "verified" in fm:
        out.extend(_check_verified(fm.get("verified"), rel))
    if "status" in fm:
        out.extend(_check_status(fm.get("status"), rel))

    # Attested-computation: if type is attested-computation, the related
    # fields are required.
    if str(type_val) == "attested-computation":
        out.extend(_check_attested_computation(fm, rel))

    return out


def _check_generated(value: Any, rel: str) -> list[Violation]:
    if not isinstance(value, dict):
        return [
            Violation(
                Level.ERROR,
                "generated.malformed",
                "'generated' must be a mapping with 'by' and 'at' (OKF §breaking)",
                path=rel,
            )
        ]
    out: list[Violation] = []
    if not value.get("by"):
        out.append(
            Violation(
                Level.WARN,
                "generated.by_missing",
                "'generated.by' should name the producing actor",
                path=rel,
            )
        )
    if not value.get("at"):
        out.append(
            Violation(
                Level.WARN,
                "generated.at_missing",
                "'generated.at' should record the last-change timestamp",
                path=rel,
            )
        )
    return out


def _check_sources(value: Any, rel: str) -> list[Violation]:
    """``sources`` is a list. Each entry is a mapping or a string."""
    if not isinstance(value, list):
        return [
            Violation(
                Level.ERROR,
                "sources.malformed",
                "'sources' must be a list (each entry is a mapping or string)",
                path=rel,
            )
        ]
    out: list[Violation] = []
    for i, entry in enumerate(value):
        if isinstance(entry, str):
            continue  # bare string is the legacy wiki shape — informational
        if isinstance(entry, dict):
            if not entry:
                out.append(
                    Violation(
                        Level.WARN,
                        "sources.entry_empty",
                        f"sources[{i}] is an empty mapping",
                        path=rel,
                    )
                )
            continue
        out.append(
            Violation(
                Level.ERROR,
                "sources.entry_malformed",
                f"sources[{i}] must be a mapping or string, got {type(entry).__name__}",
                path=rel,
            )
        )
    return out


def _check_verified(value: Any, rel: str) -> list[Violation]:
    if not isinstance(value, list):
        return [
            Violation(
                Level.ERROR,
                "verified.malformed",
                "'verified' must be a list of {by, at} entries",
                path=rel,
            )
        ]
    out: list[Violation] = []
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            out.append(
                Violation(
                    Level.ERROR,
                    "verified.entry_malformed",
                    f"verified[{i}] must be a mapping with 'by' and 'at'",
                    path=rel,
                )
            )
            continue
        if not entry.get("by") or not entry.get("at"):
            out.append(
                Violation(
                    Level.WARN,
                    "verified.entry_incomplete",
                    f"verified[{i}] should declare both 'by' and 'at'",
                    path=rel,
                )
            )
    return out


def _check_status(value: Any, rel: str) -> list[Violation]:
    if not isinstance(value, str) or value not in KNOWN_STATUS:
        return [
            Violation(
                Level.ERROR,
                "status.malformed",
                f"'status' must be one of {sorted(KNOWN_STATUS)}",
                path=rel,
            )
        ]
    return []


def _check_attested_computation(fm: dict, rel: str) -> list[Violation]:
    """OKF attested-computation type requires a small key set."""
    required = ("runtime", "parameters", "computation", "executor", "attester")
    out: list[Violation] = []
    for key in required:
        if key not in fm:
            out.append(
                Violation(
                    Level.ERROR,
                    f"attested.{key}_missing",
                    f"attested-computation concept must declare '{key}'",
                    path=rel,
                )
            )
    return out