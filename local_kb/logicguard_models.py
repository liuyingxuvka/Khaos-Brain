from __future__ import annotations

import hashlib
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
import json
import os
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from local_kb.common import normalize_string_list, normalize_text, safe_float, utc_now_iso


MIN_RESEARCHGUARD_VERSION = "0.1.1"
LOGICGUARD_AUTHORITY_SCHEMA = "khaos-brain.logicguard-authority.v1"
AUTHORITY_GENERATION_POINTER_SCHEMA = "khaos-brain.logicguard-authority-generation.v1"
LOGICGUARD_AUTHORITY_ROOT = Path(".local") / "khaos-brain" / "logicguard-authority"
AUTHORITY_SCOPES = ("public", "private", "candidates")
ROOT_CLAIM_NODE_ID = "claim-root"
ROOT_ARGUMENT_BLOCK_ID = "card-argument"
MODEL_ID_PREFIX = "khaos-card"
MESH_ID_PREFIX = "khaos-brain"
AUTHORITY_GENERATION_WRITERS = {
    "local_kb.maintenance_migration",
    "local_kb.lifecycle.run_incremental_sleep",
}
PROJECTION_EXTENSION_EXCLUDED_FIELDS = {
    "id", "title", "type", "scope", "domain_path", "cross_index",
    "related_cards", "tags", "trigger_keywords", "if", "action", "predict",
    "use", "confidence", "source", "status", "updated_at", "i18n", "then",
    "evidence", "warrant", "warrants", "assumption", "assumptions",
    "rebuttal", "rebuttals", "limitations", "qualifiers", "boundary_conditions",
    "projection_schema_version", "projection_digest", "authority_generation_id",
    "authority_scope", "logicguard_model_id", "logicguard_node_id",
    "logicguard_block_id", "logicguard_revision_id", "logicguard_mesh_id",
    "logicguard_mesh_revision_id", "logicguard_open_role_gaps",
}

REQUIRED_LOGICGUARD_SYMBOLS = (
    "ArgumentBlock",
    "CrossModelEdge",
    "Edge",
    "FileModelMeshStore",
    "FileModelStore",
    "LogicModel",
    "MeshMaterializationRequest",
    "MeshMembership",
    "MeshNodeOverride",
    "MeshSimulationDelta",
    "ModelMeshDefinition",
    "ModelRegistryEntry",
    "Node",
    "ProvenanceRecord",
    "QualifiedModelRef",
    "QualifiedNodeRef",
    "evaluate_materialized_mesh",
    "load_model_from_dict",
    "materialize_mesh",
    "simulate_mesh",
    "validate_model",
    "validate_model_payload",
)

GROUNDING_ORIGIN_KINDS = {
    "external_source",
    "observed_event",
    "user_attestation",
    "test_result",
    "human_observation",
    "instrument_measurement",
}


class LogicGuardDependencyError(RuntimeError):
    pass


class AuthorityScopeError(ValueError):
    pass


class ExactBindingError(RuntimeError):
    pass


class UngroundedRelationshipError(ValueError):
    pass


@dataclass(frozen=True)
class LogicGuardBinding:
    authority_scope: str
    model_id: str
    node_id: str
    block_id: str
    revision_id: str
    mesh_id: str = ""
    mesh_revision_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "authority_scope": self.authority_scope,
            "logicguard_model_id": self.model_id,
            "logicguard_node_id": self.node_id,
            "logicguard_block_id": self.block_id,
            "logicguard_revision_id": self.revision_id,
            "logicguard_mesh_id": self.mesh_id,
            "logicguard_mesh_revision_id": self.mesh_revision_id,
        }


@dataclass(frozen=True)
class ModelCommitResult:
    binding: LogicGuardBinding
    receipt: Mapping[str, Any]
    content_digest: str
    model_payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding": self.binding.to_dict(),
            "receipt": dict(self.receipt),
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class MeshCommitResult:
    mesh_id: str
    mesh_revision_id: str
    content_digest: str
    receipt: Mapping[str, Any]
    bindings: tuple[LogicGuardBinding, ...]
    unresolved_relationships: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mesh_id": self.mesh_id,
            "mesh_revision_id": self.mesh_revision_id,
            "content_digest": self.content_digest,
            "receipt": dict(self.receipt),
            "bindings": [item.to_dict() for item in self.bindings],
            "unresolved_relationships": [dict(item) for item in self.unresolved_relationships],
        }


@dataclass(frozen=True)
class GroundedModelRelation:
    relation_id: str
    source: LogicGuardBinding
    target: LogicGuardBinding
    edge_type: str
    explanation: str
    provenance: tuple[Mapping[str, Any], ...]
    weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GroundedMembership:
    owner: LogicGuardBinding
    logical_model: LogicGuardBinding
    roles: tuple[str, ...]
    provenance: tuple[Mapping[str, Any], ...]
    role_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelNeighborhood:
    binding: LogicGuardBinding
    materialized: Mapping[str, Any]
    evaluation: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding": self.binding.to_dict(),
            "materialized": dict(self.materialized),
            "evaluation": dict(self.evaluation),
        }


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in re.findall(r"\d+", str(value))[:3])


def _researchguard_logic_module() -> Any:
    try:
        from researchguard import logic as research_logic
    except Exception as exc:  # pragma: no cover - exercised by installer subprocess tests
        raise LogicGuardDependencyError(
            f"ResearchGuard logic member import failed: {type(exc).__name__}: {exc}"
        ) from exc
    return research_logic


def retired_standalone_logicguard_residuals() -> dict[str, Any]:
    """Inspect retired distribution/import authority without importing it."""

    issues: list[str] = []
    distribution: dict[str, Any] = {
        "present": False,
        "version": "",
        "location": "",
        "direct_url": {},
    }
    try:
        installed = importlib_metadata.distribution("logicguard")
    except importlib_metadata.PackageNotFoundError:
        installed = None
    except Exception as exc:
        installed = None
        issues.append(
            "retired LogicGuard distribution lookup failed: "
            f"{type(exc).__name__}: {exc}"
        )
    if installed is not None:
        direct_url: dict[str, Any] = {}
        try:
            raw_direct_url = installed.read_text("direct_url.json")
            parsed_direct_url = (
                json.loads(raw_direct_url)
                if raw_direct_url
                else {}
            )
            if isinstance(parsed_direct_url, Mapping):
                direct_url = dict(parsed_direct_url)
        except (OSError, json.JSONDecodeError, TypeError):
            direct_url = {}
        distribution = {
            "present": True,
            "version": str(installed.version or ""),
            "location": str(Path(installed.locate_file("")).resolve()),
            "direct_url": json_safe(direct_url),
        }
        issues.append("retired standalone LogicGuard distribution is installed")

    import_resolution: dict[str, Any] = {
        "present": False,
        "origin": "",
        "locations": [],
        "error": "",
    }
    try:
        spec = importlib_util.find_spec("logicguard")
    except Exception as exc:
        spec = None
        import_resolution["error"] = f"{type(exc).__name__}: {exc}"
        issues.append(
            "retired LogicGuard import resolution could not be proven absent"
        )
    if spec is not None:
        locations = [
            str(Path(item).resolve())
            for item in (spec.submodule_search_locations or ())
        ]
        import_resolution = {
            "present": True,
            "origin": str(getattr(spec, "origin", "") or ""),
            "locations": locations,
            "error": "",
        }
        issues.append("retired standalone LogicGuard import origin is resolvable")

    runtime_modules = sorted(
        name
        for name in sys.modules
        if name == "logicguard" or name.startswith("logicguard.")
    )
    if runtime_modules:
        issues.append("retired standalone LogicGuard modules are loaded")
    return {
        "schema_version": (
            "khaos-brain.retired-standalone-logicguard-residuals.v1"
        ),
        "ok": not issues,
        "distribution": distribution,
        "import_resolution": import_resolution,
        "runtime_modules": runtime_modules,
        "issues": issues,
        "claim_boundary": (
            "This check proves only that the active Python environment has no "
            "standalone LogicGuard distribution, import origin, or loaded "
            "module. The retained Codex logicguard member Skill is a separate "
            "ResearchGuard consumer projection."
        ),
    }


def researchguard_logic_dependency_preflight(
    *,
    strict: bool = True,
    require_no_retired_standalone: bool = False,
) -> dict[str, Any]:
    try:
        research_logic = _researchguard_logic_module()
        origin = str(getattr(research_logic, "__file__", "") or "")
        version = str(getattr(research_logic, "__version__", "") or "")
        missing = tuple(
            name
            for name in REQUIRED_LOGICGUARD_SYMBOLS
            if not hasattr(research_logic, name)
        )
        issues: list[str] = []
        if not origin:
            issues.append(
                "ResearchGuard logic member resolved to an empty namespace "
                "instead of the installed package"
            )
        if _version_tuple(version) < _version_tuple(MIN_RESEARCHGUARD_VERSION):
            issues.append(
                f"ResearchGuard {MIN_RESEARCHGUARD_VERSION}+ is required; "
                f"found {version or 'unknown'}"
            )
        if missing:
            issues.append(
                "ResearchGuard logic public API is incomplete: " + ", ".join(missing)
            )
        if (
            str(getattr(research_logic, "SCHEMA_VERSION", ""))
            != "researchguard.logic.model-store.v1"
        ):
            issues.append("ResearchGuard logic model-store schema is unsupported")
        if (
            str(getattr(research_logic, "MESH_SCHEMA_VERSION", ""))
            != "researchguard.logic.model-mesh.v1"
        ):
            issues.append("ResearchGuard logic ModelMesh schema is unsupported")
        retired_standalone = retired_standalone_logicguard_residuals()
        if (
            require_no_retired_standalone
            and not retired_standalone.get("ok")
        ):
            issues.extend(
                f"retired-standalone:{item}"
                for item in retired_standalone.get("issues", [])
            )
        payload = {
            "ok": not issues,
            "version": version,
            "origin": origin,
            "model_store_schema": str(
                getattr(research_logic, "SCHEMA_VERSION", "")
            ),
            "mesh_schema": str(
                getattr(research_logic, "MESH_SCHEMA_VERSION", "")
            ),
            "mesh_store_tool_fingerprint": str(
                getattr(research_logic, "MESH_STORE_TOOL_FINGERPRINT", "")
            ),
            "mesh_evaluator_fingerprint": str(
                getattr(research_logic, "MESH_EVALUATOR_FINGERPRINT", "")
            ),
            "mesh_simulator_fingerprint": str(
                getattr(research_logic, "MESH_SIMULATOR_FINGERPRINT", "")
            ),
            "missing_symbols": list(missing),
            "retired_standalone_logicguard": retired_standalone,
            "issues": issues,
        }
    except LogicGuardDependencyError as exc:
        payload = {
            "ok": False,
            "version": "",
            "origin": "",
            "model_store_schema": "",
            "mesh_schema": "",
            "mesh_store_tool_fingerprint": "",
            "mesh_evaluator_fingerprint": "",
            "mesh_simulator_fingerprint": "",
            "missing_symbols": list(REQUIRED_LOGICGUARD_SYMBOLS),
            "retired_standalone_logicguard": (
                retired_standalone_logicguard_residuals()
            ),
            "issues": [str(exc)],
        }
    if strict and not payload["ok"]:
        raise LogicGuardDependencyError("; ".join(payload["issues"]))
    return payload


def normalize_authority_scope(scope: str) -> str:
    normalized = str(scope or "").strip().lower()
    if normalized == "candidate":
        normalized = "candidates"
    if normalized not in AUTHORITY_SCOPES:
        raise AuthorityScopeError(f"Unsupported LogicGuard authority scope: {scope!r}")
    return normalized


def authority_root(repo_root: Path) -> Path:
    return Path(repo_root) / LOGICGUARD_AUTHORITY_ROOT


def authority_generation_pointer_path(repo_root: Path) -> Path:
    return authority_root(repo_root) / "current-generation.json"


def authority_generation_manifest_path(repo_root: Path, generation_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(generation_id)).strip("-")
    if not safe_id:
        raise ValueError("Authority generation id is required")
    return authority_root(repo_root) / "generations" / f"{safe_id}.json"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(json_safe(dict(payload)), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_authority_generation_payload(
    *,
    generation_id: str,
    scope_meshes: Mapping[str, Mapping[str, Any]],
    projection_manifest_digest: str,
    projection_count: int,
    actor: str,
) -> dict[str, Any]:
    normalized_meshes: dict[str, dict[str, Any]] = {}
    for scope, value in sorted(scope_meshes.items()):
        normalized = normalize_authority_scope(scope)
        normalized_meshes[normalized] = {
            "mesh_id": str(value.get("mesh_id") or ""),
            "mesh_revision_id": str(value.get("mesh_revision_id") or ""),
            "content_digest": str(value.get("content_digest") or ""),
        }
        if not all(normalized_meshes[normalized].values()):
            raise ValueError(f"Authority generation has an incomplete mesh binding for {normalized}")
    if not normalized_meshes and int(projection_count) != 0:
        raise ValueError("A non-empty authority generation requires at least one scoped mesh")
    preflight = researchguard_logic_dependency_preflight()
    payload = {
        "schema_version": AUTHORITY_GENERATION_POINTER_SCHEMA,
        "generation_id": str(generation_id),
        "status": "current",
        "activated_at": utc_now_iso(),
        "actor": actor,
        "scope_meshes": normalized_meshes,
        "projection_manifest_digest": str(projection_manifest_digest),
        "projection_count": int(projection_count),
        "researchguard_version": preflight["version"],
        "researchguard_logic_model_store_schema": preflight["model_store_schema"],
        "researchguard_logic_mesh_schema": preflight["mesh_schema"],
        "researchguard_logic_mesh_store_tool_fingerprint": preflight[
            "mesh_store_tool_fingerprint"
        ],
    }
    unsigned = {key: value for key, value in payload.items() if key not in {"activated_at", "pointer_digest"}}
    payload["pointer_digest"] = "sha256:" + canonical_digest(unsigned)
    return payload


def publish_authority_generation(
    repo_root: Path,
    payload: Mapping[str, Any],
    *,
    writer: str,
) -> dict[str, Any]:
    if writer not in AUTHORITY_GENERATION_WRITERS:
        raise PermissionError(f"Unauthorized authority-generation writer: {writer}")
    validated = validate_authority_generation_payload(payload)
    generation_path = authority_generation_manifest_path(repo_root, str(validated["generation_id"]))
    if generation_path.exists():
        try:
            existing = validate_authority_generation_payload(
                json.loads(generation_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, ExactBindingError) as exc:
            raise ExactBindingError(f"Existing authority generation is corrupt: {exc}") from exc
        if existing["pointer_digest"] != validated["pointer_digest"]:
            raise ExactBindingError("Authority generation id cannot be rebound to different content")
        validated = existing
    else:
        _atomic_write_json(generation_path, validated)
    _atomic_write_json(authority_generation_pointer_path(repo_root), validated)
    # Publication changes the sole normal-runtime authority. Drop every
    # process-local immutable read session immediately so old generations do
    # not retain large mesh views or answer a later read.
    _clear_bound_read_caches()
    return validated


def validate_authority_generation_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = json_safe(dict(payload))
    issues: list[str] = []
    if value.get("schema_version") != AUTHORITY_GENERATION_POINTER_SCHEMA:
        issues.append("authority generation schema is missing or unsupported")
    if value.get("status") != "current":
        issues.append("authority generation status is not current")
    if not str(value.get("generation_id") or ""):
        issues.append("authority generation id is missing")
    unsigned = {key: item for key, item in value.items() if key not in {"activated_at", "pointer_digest"}}
    expected_digest = "sha256:" + canonical_digest(unsigned)
    if str(value.get("pointer_digest") or "") != expected_digest:
        issues.append("authority generation pointer digest mismatch")
    scopes = value.get("scope_meshes") if isinstance(value.get("scope_meshes"), Mapping) else {}
    projection_count = int(value.get("projection_count") or 0)
    if projection_count < 0:
        issues.append("authority generation projection count is negative")
    if not scopes and projection_count != 0:
        issues.append("non-empty authority generation has no scoped meshes")
    for scope, binding in scopes.items():
        try:
            normalize_authority_scope(str(scope))
        except AuthorityScopeError:
            issues.append(f"authority generation has an unsupported scope: {scope}")
            continue
        if not isinstance(binding, Mapping) or not all(
            str(binding.get(field) or "")
            for field in ("mesh_id", "mesh_revision_id", "content_digest")
        ):
            issues.append(f"authority generation has an incomplete mesh binding for {scope}")
    if issues:
        raise ExactBindingError("; ".join(issues))
    return value


def load_authority_generation(repo_root: Path) -> dict[str, Any]:
    path = authority_generation_pointer_path(repo_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExactBindingError(f"Current LogicGuard authority generation is unavailable: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ExactBindingError("Current LogicGuard authority generation is not an object")
    return validate_authority_generation_payload(payload)


def model_store_root(repo_root: Path, scope: str) -> Path:
    return authority_root(repo_root) / normalize_authority_scope(scope) / "models"


def mesh_store_root(repo_root: Path, scope: str) -> Path:
    return authority_root(repo_root) / normalize_authority_scope(scope) / "meshes"


def open_model_store(repo_root: Path, scope: str) -> Any:
    logicguard = _researchguard_logic_module()
    researchguard_logic_dependency_preflight()
    return logicguard.FileModelStore(model_store_root(repo_root, scope))


def open_pinned_model_read_store(
    repo_root: Path,
    scope: str,
) -> tuple[Any, frozenset[str]]:
    """Open one exact read session against the sole current store manifest.

    LogicGuard's public ``get`` and ``head`` methods deliberately reload their
    manifest on every call. That is appropriate for independent reads, but a
    generation-wide audit over thousands of immutable revisions would reread
    the same manifest thousands of times. A pinned session still delegates
    authorization and snapshot verification to the real LogicGuard store; it
    only supplies the same already-validated manifest to those repeated reads.
    It must never be used to create a new revision. If the current LogicGuard
    store no longer exposes this hook, fail visibly instead of adding a second
    reader or fallback layout.
    """

    store = open_model_store(repo_root, scope)
    loader = getattr(store, "_load_manifest", None)
    if not callable(loader):
        raise LogicGuardDependencyError(
            "LogicGuard FileModelStore lacks the required current-manifest read hook"
        )
    manifest = loader()
    if not isinstance(manifest, Mapping):
        raise LogicGuardDependencyError("LogicGuard current model manifest is not an object")
    idempotency = manifest.get("idempotency")
    if not isinstance(idempotency, Mapping):
        raise LogicGuardDependencyError(
            "LogicGuard current model manifest lacks its idempotency authority"
        )

    def pinned_manifest() -> Mapping[str, Any]:
        return manifest

    setattr(store, "_load_manifest", pinned_manifest)
    return store, frozenset(str(item) for item in idempotency)


def open_mesh_store(
    repo_root: Path,
    scope: str,
    *,
    model_store: Any | None = None,
) -> Any:
    logicguard = _researchguard_logic_module()
    normalized = normalize_authority_scope(scope)
    return logicguard.FileModelMeshStore(
        mesh_store_root(repo_root, normalized),
        model_store=model_store or open_model_store(repo_root, normalized),
    )


def open_pinned_mesh_read_store(
    repo_root: Path,
    scope: str,
    *,
    model_store: Any,
) -> Any:
    """Open one exact mesh read session pinned to its current manifest.

    The authority-generation pointer, exact mesh revision, and immutable model
    revisions remain the freshness boundary.  Pinning only prevents repeated
    reads of the same already-validated manifest inside that generation; it
    neither authorizes writes nor creates an alternate reader.
    """

    store = open_mesh_store(repo_root, scope, model_store=model_store)
    loader = getattr(store, "_load_manifest", None)
    if not callable(loader):
        raise LogicGuardDependencyError(
            "LogicGuard FileModelMeshStore lacks the required current-manifest read hook"
        )
    manifest = loader()
    if not isinstance(manifest, Mapping):
        raise LogicGuardDependencyError("LogicGuard current mesh manifest is not an object")

    def pinned_manifest() -> Mapping[str, Any]:
        return manifest

    setattr(store, "_load_manifest", pinned_manifest)
    return store


@lru_cache(maxsize=32)
def _cached_bound_read_session(
    repo_root: str,
    authority_pointer_digest: str,
    authority_scope: str,
) -> tuple[Any, Any]:
    """Reuse read-only stores only within one exact authority generation."""

    if not authority_pointer_digest:
        raise ExactBindingError("Current authority generation lacks its pointer digest")
    root = Path(repo_root)
    scope = normalize_authority_scope(authority_scope)
    model_store, _idempotency_keys = open_pinned_model_read_store(root, scope)
    mesh_store = open_pinned_mesh_read_store(
        root,
        scope,
        model_store=model_store,
    )
    return model_store, mesh_store


@lru_cache(maxsize=len(AUTHORITY_SCOPES))
def _cached_current_mesh_view(
    repo_root: str,
    authority_pointer_digest: str,
    authority_scope: str,
    mesh_id: str,
    mesh_revision_id: str,
) -> Any:
    """Open one immutable mesh view per exact current generation and scope.

    A card context previously reparsed the same scope mesh three times: for
    binding validation, neighborhood validation, and materialization. Large
    local brains make that repeated work the dominant latency. This cache is
    generation-, scope-, mesh-, and revision-bound; publication changes the
    pointer digest and clears it. There is no alternate reader or head lookup.
    """

    if not authority_pointer_digest:
        raise ExactBindingError("Current authority generation lacks its pointer digest")
    _model_store, mesh_store = _cached_bound_read_session(
        repo_root,
        authority_pointer_digest,
        authority_scope,
    )
    return mesh_store.open_view(mesh_id, mesh_revision_id)


def _clear_bound_read_caches() -> None:
    """Release all process-local reads when the sole authority changes."""

    _cached_bound_argument_context_json.cache_clear()
    _cached_current_mesh_view.cache_clear()
    _cached_bound_read_session.cache_clear()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _slug(value: str, *, limit: int = 48) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return (normalized or "card")[:limit].rstrip("-")


def model_id_for_card(card_id: str) -> str:
    card_id = str(card_id or "").strip()
    if not card_id:
        raise ValueError("A stable card id is required for LogicGuard model identity")
    return f"{MODEL_ID_PREFIX}-{_slug(card_id)}-{hashlib.sha256(card_id.encode('utf-8')).hexdigest()[:12]}"


def mesh_id_for_scope(scope: str) -> str:
    return f"{MESH_ID_PREFIX}-{normalize_authority_scope(scope)}"


def _source_items(card: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    source = card.get("source")
    if isinstance(source, Mapping):
        return [dict(source)]
    if isinstance(source, list):
        return [dict(item) for item in source if isinstance(item, Mapping)]
    return []


def _origin_kind(origin: str) -> str:
    value = str(origin or "").lower()
    if "direct user" in value or "user instruction" in value or "explicit user" in value:
        return "user_attestation"
    if "test" in value or "fixture" in value:
        return "test_result"
    if "observ" in value or "event" in value:
        return "observed_event"
    if "human" in value or "practice" in value:
        return "human_observation"
    if "http" in value or "paper" in value or "report" in value:
        return "external_source"
    return "imported_record"


def _provenance_record(
    *,
    origin_kind: str,
    content: Any,
    source_id: str,
    source_reference: str,
    source_date: str = "",
    actor: str,
) -> Any:
    logicguard = _researchguard_logic_module()
    return logicguard.ProvenanceRecord(
        origin_kind=origin_kind,
        content_hash="sha256:" + canonical_digest(content),
        source_id=source_id,
        source_reference=source_reference or None,
        source_date=source_date or None,
        actor=actor,
    )


def card_provenance(
    card: Mapping[str, Any],
    *,
    source_reference: str = "",
    actor: str = "khaos-brain-model-builder",
) -> tuple[Any, ...]:
    card_id = str(card.get("id") or "")
    records: list[Any] = []
    for index, source in enumerate(_source_items(card), start=1):
        origin = str(source.get("origin") or source.get("kind") or "legacy card source")
        records.append(
            _provenance_record(
                origin_kind=_origin_kind(origin),
                content=source,
                source_id=f"card:{card_id}:source:{index}",
                source_reference=source_reference,
                source_date=str(source.get("date") or source.get("source_date") or ""),
                actor=actor,
            )
        )
    if not records:
        records.append(
            _provenance_record(
                origin_kind="imported_record",
                content=dict(card),
                source_id=f"card:{card_id}:legacy-record",
                source_reference=source_reference,
                actor=actor,
            )
        )
    return tuple(records)


def _text_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Mapping):
        text = normalize_text(
            value.get("text")
            or value.get("description")
            or value.get("result")
            or value.get("observation")
            or value.get("notes")
        ).strip()
        return [text] if text else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_text_items(item))
        return result
    text = normalize_text(value).strip()
    return [text] if text else []


def _explicit_evidence(card: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any] | None]]:
    raw = card.get("evidence")
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    result: list[tuple[str, Mapping[str, Any] | None]] = []
    for item in values:
        if isinstance(item, Mapping):
            texts = _text_items(item)
            result.extend((text, item) for text in texts)
        else:
            result.extend((text, None) for text in _text_items(item))
    return result


def _node_provenance_for_evidence(
    card: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    text: str,
    index: int,
    source_reference: str,
    actor: str,
) -> list[Any]:
    if evidence:
        origin = str(evidence.get("origin") or evidence.get("kind") or "legacy explicit evidence")
        return [
            _provenance_record(
                origin_kind=_origin_kind(origin),
                content=evidence,
                source_id=str(evidence.get("source_id") or f"card:{card.get('id')}:evidence:{index}"),
                source_reference=str(evidence.get("source_reference") or source_reference),
                source_date=str(evidence.get("date") or evidence.get("source_date") or ""),
                actor=actor,
            )
        ]
    return [
        _provenance_record(
            origin_kind="imported_record",
            content=text,
            source_id=f"card:{card.get('id')}:evidence:{index}",
            source_reference=source_reference,
            actor=actor,
        )
    ]


def build_predictive_argument_model(
    card: Mapping[str, Any],
    *,
    authority_scope: str,
    source_reference: str = "",
    actor: str = "khaos-brain-model-builder",
) -> Any:
    logicguard = _researchguard_logic_module()
    researchguard_logic_dependency_preflight()
    scope = normalize_authority_scope(authority_scope)
    card_id = str(card.get("id") or "").strip()
    if not card_id:
        raise ValueError("Card id is required")
    context_text = normalize_text(
        card.get("if", {}).get("notes") if isinstance(card.get("if"), Mapping) else card.get("if")
    ).strip()
    action_text = normalize_text(
        card.get("action", {}).get("description")
        if isinstance(card.get("action"), Mapping)
        else card.get("action")
    ).strip()
    predict = card.get("predict") if isinstance(card.get("predict"), Mapping) else {}
    claim_text = normalize_text(predict.get("expected_result") if predict else card.get("predict")).strip()
    guidance = normalize_text(
        card.get("use", {}).get("guidance") if isinstance(card.get("use"), Mapping) else card.get("use")
    ).strip()
    if not claim_text:
        raise ValueError(f"Card {card_id} has no predictive root claim")

    structured_extension_fields: dict[str, dict[str, Any]] = {}
    structured_known_fields = {
        "if": {"notes"},
        "action": {"description"},
        "predict": {"expected_result", "alternatives"},
        "use": {"guidance"},
    }
    for block_name, known_fields in structured_known_fields.items():
        raw_block = card.get(block_name)
        if not isinstance(raw_block, Mapping):
            continue
        extras = {
            str(key): json_safe(value)
            for key, value in raw_block.items()
            if str(key) not in known_fields
        }
        if extras:
            structured_extension_fields[block_name] = extras

    confidence = max(0.0, min(1.0, safe_float(card.get("confidence", 0.5), 0.5)))
    provenance = card_provenance(card, source_reference=source_reference, actor=actor)
    nodes: dict[str, Any] = {}
    edges: list[Any] = []
    input_nodes: list[str] = []
    internal_nodes: list[str] = []
    assumption_ids: list[str] = []
    rebuttal_ids: list[str] = []

    def add_node(node_id: str, node_type: str, text: str, *, role: str, node_provenance: Sequence[Any] = ()) -> None:
        nodes[node_id] = logicguard.Node(
            id=node_id,
            type=node_type,
            text=text,
            scope=scope,
            confidence=confidence,
            importance=0.9 if node_id == ROOT_CLAIM_NODE_ID else 0.6,
            role=role,
            metadata={"projection_role": role, "card_id": card_id},
            provenance=list(node_provenance),
        )

    add_node(
        ROOT_CLAIM_NODE_ID,
        "Claim",
        claim_text,
        role="predicted_result",
        node_provenance=provenance,
    )
    if context_text:
        add_node("context", "Context", context_text, role="applicability_context", node_provenance=provenance)
        input_nodes.append("context")
        edges.append(logicguard.Edge("context", ROOT_CLAIM_NODE_ID, "contextualizes", explanation="Applicability context bounds the prediction."))
    if action_text:
        add_node("action", "Method", action_text, role="action_under_consideration", node_provenance=provenance)
        input_nodes.append("action")
        edges.append(logicguard.Edge("action", ROOT_CLAIM_NODE_ID, "derives", explanation="The predicted result is conditional on this action or input."))

    evidence_ids: list[str] = []
    for index, (text, item) in enumerate(_explicit_evidence(card), start=1):
        node_id = f"evidence-{index}"
        add_node(
            node_id,
            "Evidence",
            text,
            role="evidence",
            node_provenance=_node_provenance_for_evidence(
                card,
                item,
                text=text,
                index=index,
                source_reference=source_reference,
                actor=actor,
            ),
        )
        evidence_ids.append(node_id)
        input_nodes.append(node_id)
        edges.append(logicguard.Edge(node_id, ROOT_CLAIM_NODE_ID, "supports", explanation="Declared evidence supports the prediction."))

    warrant_ids: list[str] = []
    for index, text in enumerate(_text_items(card.get("warrants") or card.get("warrant")), start=1):
        node_id = f"warrant-{index}"
        add_node(node_id, "Warrant", text, role="warrant", node_provenance=provenance)
        warrant_ids.append(node_id)
        internal_nodes.append(node_id)
        edges.append(logicguard.Edge(node_id, ROOT_CLAIM_NODE_ID, "supports", explanation="Declared warrant licenses the inference."))

    for index, text in enumerate(_text_items(card.get("assumptions") or card.get("assumption")), start=1):
        node_id = f"assumption-{index}"
        add_node(node_id, "Assumption", text, role="assumption", node_provenance=provenance)
        assumption_ids.append(node_id)
        internal_nodes.append(node_id)
        edges.append(logicguard.Edge(node_id, ROOT_CLAIM_NODE_ID, "depends_on", explanation="The prediction depends on this declared assumption."))

    for index, text in enumerate(_text_items(card.get("rebuttals") or card.get("rebuttal")), start=1):
        node_id = f"rebuttal-{index}"
        add_node(node_id, "Rebuttal", text, role="rebuttal", node_provenance=provenance)
        rebuttal_ids.append(node_id)
        internal_nodes.append(node_id)
        edges.append(logicguard.Edge(node_id, ROOT_CLAIM_NODE_ID, "attacks", explanation="Declared rebuttal challenges the prediction."))

    boundary_ids: list[str] = []
    boundary_values = card.get("limitations") or card.get("qualifiers") or card.get("boundary_conditions")
    for index, text in enumerate(_text_items(boundary_values), start=1):
        node_id = f"limitation-{index}"
        add_node(node_id, "Limitation", text, role="limitation", node_provenance=provenance)
        boundary_ids.append(node_id)
        internal_nodes.append(node_id)
        edges.append(logicguard.Edge(node_id, ROOT_CLAIM_NODE_ID, "qualifies", explanation="Declared boundary limits the prediction."))

    alternatives: list[dict[str, str]] = []
    raw_alternatives = predict.get("alternatives", []) if isinstance(predict, Mapping) else []
    for index, item in enumerate(raw_alternatives if isinstance(raw_alternatives, list) else [], start=1):
        if not isinstance(item, Mapping):
            continue
        when_text = normalize_text(item.get("when")).strip()
        result_text = normalize_text(item.get("result")).strip()
        if not result_text:
            continue
        alt_claim = f"alternative-claim-{index}"
        add_node(alt_claim, "Claim", result_text, role="alternative_result", node_provenance=provenance)
        internal_nodes.append(alt_claim)
        if when_text:
            alt_context = f"alternative-context-{index}"
            add_node(alt_context, "Context", when_text, role="alternative_context", node_provenance=provenance)
            internal_nodes.append(alt_context)
            edges.append(logicguard.Edge(alt_context, alt_claim, "contextualizes", explanation="Alternative condition bounds the alternative result."))
        edges.append(logicguard.Edge(alt_claim, ROOT_CLAIM_NODE_ID, "qualifies", explanation="Alternative branch qualifies the main prediction."))
        alternatives.append({"when": when_text, "result": result_text})

    open_role_gaps = tuple(
        role
        for role, present in (
            ("context", bool(context_text)),
            ("action", bool(action_text)),
            ("evidence", bool(evidence_ids)),
            ("warrant", bool(warrant_ids)),
            ("assumption", bool(assumption_ids)),
            ("opposition", bool(rebuttal_ids)),
            ("boundary", bool(boundary_ids or alternatives)),
        )
        if not present
    )
    edges = [
        logicguard.Edge(
            source=edge.source,
            target=edge.target,
            type=edge.type,
            weight=edge.weight,
            explanation=edge.explanation,
            importance=edge.importance,
            salience=edge.salience,
            importance_reason=edge.importance_reason,
            metadata=dict(edge.metadata),
            id=(
                edge.id
                or f"edge-{index:03d}-{_slug(edge.source, limit=20)}-"
                f"{_slug(edge.type, limit=16)}-{_slug(edge.target, limit=20)}"
            ),
        )
        for index, edge in enumerate(edges, start=1)
    ]
    block = logicguard.ArgumentBlock(
        id=ROOT_ARGUMENT_BLOCK_ID,
        title=str(card.get("title") or card_id),
        level="card",
        input_nodes=input_nodes,
        internal_nodes=internal_nodes,
        output_claims=[ROOT_CLAIM_NODE_ID],
        local_assumptions=assumption_ids,
        local_rebuttals=rebuttal_ids,
        acceptance_conditions={"root_claim": ROOT_CLAIM_NODE_ID},
        diagnostics=[f"missing_role:{role}" for role in open_role_gaps],
        root_claim=ROOT_CLAIM_NODE_ID,
        member_nodes=list(nodes),
        metadata={
            "model_card_role": "argument_card",
            "card_id": card_id,
            "authority_scope": scope,
            "open_role_gaps": list(open_role_gaps),
        },
        provenance=list(provenance),
    )
    model_metadata = {
        "authority_schema": LOGICGUARD_AUTHORITY_SCHEMA,
        "authority_scope": scope,
        "card_id": card_id,
        "card_type": str(card.get("type") or "model"),
        "declared_scope": str(card.get("scope") or ("private" if scope == "private" else "public")),
        "status": str(card.get("status") or "candidate"),
        "confidence": confidence,
        "domain_path": normalize_string_list(card.get("domain_path")),
        "cross_index": normalize_string_list(card.get("cross_index")),
        "tags": normalize_string_list(card.get("tags")),
        "trigger_keywords": normalize_string_list(card.get("trigger_keywords")),
        "operational_guidance": guidance,
        "updated_at": str(card.get("updated_at") or ""),
        "display_source": json_safe(card.get("source") or []),
        "i18n": json_safe(card.get("i18n") if isinstance(card.get("i18n"), Mapping) else {}),
        "alternatives": alternatives,
        "open_role_gaps": list(open_role_gaps),
        "legacy_related_card_candidates": normalize_string_list(card.get("related_cards")),
        "legacy_content_digest": canonical_digest(dict(card)),
        "projection_extensions": {
            str(key): json_safe(value)
            for key, value in sorted(card.items(), key=lambda item: str(item[0]))
            if str(key) not in PROJECTION_EXTENSION_EXCLUDED_FIELDS
        },
        "structured_extension_fields": structured_extension_fields,
        "builder": "local_kb.logicguard_models:v1",
    }
    model = logicguard.LogicModel(
        id=model_id_for_card(card_id),
        title=str(card.get("title") or card_id),
        root_claim=ROOT_CLAIM_NODE_ID,
        nodes=nodes,
        edges=edges,
        acceptance={
            ROOT_CLAIM_NODE_ID: {
                "scope_match": True,
                "warrant_required": True,
                "no_undefeated_rebuttal": True,
            }
        },
        hierarchy={},
        blocks={ROOT_ARGUMENT_BLOCK_ID: block},
        metadata=model_metadata,
    )
    payload = model.canonical_dict()
    logicguard.validate_model_payload(payload)
    validation = logicguard.validate_model(logicguard.load_model_from_dict(payload), durable=True)
    if not bool(getattr(validation, "ok", False)):
        issues = getattr(validation, "issues", ())
        raise ValueError("LogicGuard model validation failed: " + "; ".join(str(item) for item in issues))
    return model


def commit_card_model(
    repo_root: Path,
    card: Mapping[str, Any],
    *,
    authority_scope: str,
    expected_revision: str | None,
    idempotency_key: str,
    actor: str,
    source_reference: str = "",
    model_store: Any | None = None,
) -> ModelCommitResult:
    scope = normalize_authority_scope(authority_scope)
    model = build_predictive_argument_model(
        card,
        authority_scope=scope,
        source_reference=source_reference,
        actor=actor,
    )
    payload = model.canonical_dict()
    store = model_store or open_model_store(repo_root, scope)
    transaction = store.begin(model.id, expected_revision, idempotency_key, actor)
    transaction.stage(payload)
    receipt = transaction.commit()
    snapshot = store.get(model.id, receipt.revision)
    binding = LogicGuardBinding(
        authority_scope=scope,
        model_id=str(snapshot.model_id),
        node_id=ROOT_CLAIM_NODE_ID,
        block_id=ROOT_ARGUMENT_BLOCK_ID,
        revision_id=str(snapshot.revision),
    )
    return ModelCommitResult(
        binding=binding,
        receipt=receipt.to_dict(),
        content_digest=str(snapshot.content_digest),
        model_payload=snapshot.authoring_payload(),
    )


def reuse_card_model_if_exact(
    card: Mapping[str, Any],
    *,
    authority_scope: str,
    actor: str,
    source_reference: str,
    model_store: Any,
) -> ModelCommitResult | None:
    """Reuse a current immutable head only when canonical model content is equal."""

    scope = normalize_authority_scope(authority_scope)
    expected_model = build_predictive_argument_model(
        card,
        authority_scope=scope,
        source_reference=source_reference,
        actor=actor,
    )
    head = model_store.head(expected_model.id)
    if head is None:
        return None
    snapshot = model_store.get(expected_model.id, head)
    if snapshot.to_model().canonical_dict() != expected_model.canonical_dict():
        return None
    binding = LogicGuardBinding(
        authority_scope=scope,
        model_id=str(snapshot.model_id),
        node_id=ROOT_CLAIM_NODE_ID,
        block_id=ROOT_ARGUMENT_BLOCK_ID,
        revision_id=str(snapshot.revision),
    )
    return ModelCommitResult(
        binding=binding,
        receipt={
            "status": "reused-canonical-equivalent-head",
            "model_id": str(snapshot.model_id),
            "revision": str(snapshot.revision),
            "content_digest": str(snapshot.content_digest),
            "claim_boundary": (
                "The current builder reproduced the exact canonical LogicGuard model; "
                "no new revision was required."
            ),
        },
        content_digest=str(snapshot.content_digest),
        model_payload=snapshot.authoring_payload(),
    )


def read_exact_model(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    model_store: Any | None = None,
) -> Any:
    scope = normalize_authority_scope(binding.authority_scope)
    if not binding.model_id or not binding.revision_id:
        raise ExactBindingError("Exact model id and revision are required")
    store = model_store or open_model_store(repo_root, scope)
    try:
        snapshot = store.get(binding.model_id, binding.revision_id)
    except Exception as exc:
        raise ExactBindingError(
            f"Exact LogicGuard revision is unavailable for {binding.model_id}@{binding.revision_id}: {exc}"
        ) from exc
    payload = snapshot.authoring_payload()
    metadata = payload.get("model", {}).get("metadata", {}) if isinstance(payload.get("model"), Mapping) else {}
    # LogicModel.to_dict stores metadata alongside title/root_claim inside model.
    if not isinstance(metadata, Mapping):
        metadata = {}
    model = snapshot.to_model()
    if str(model.metadata.get("authority_scope") or "") != scope:
        raise AuthorityScopeError("Exact model metadata crosses the requested authority scope")
    if binding.node_id not in model.nodes:
        raise ExactBindingError(f"Bound LogicGuard node is missing: {binding.node_id}")
    if binding.block_id not in model.blocks:
        raise ExactBindingError(f"Bound LogicGuard block is missing: {binding.block_id}")
    return snapshot


def _qualified_model_ref(logicguard: Any, binding: LogicGuardBinding) -> Any:
    return logicguard.QualifiedModelRef(binding.model_id, binding.revision_id)


def _qualified_node_ref(logicguard: Any, binding: LogicGuardBinding) -> Any:
    return logicguard.QualifiedNodeRef(binding.model_id, binding.revision_id, binding.node_id)


def _grounding_records(records: Iterable[Mapping[str, Any]]) -> tuple[Any, ...]:
    logicguard = _researchguard_logic_module()
    coerced = logicguard.coerce_provenance(records)
    if not coerced:
        raise UngroundedRelationshipError("A cross-model relation requires provenance")
    if not any(str(record.origin_kind.value) in GROUNDING_ORIGIN_KINDS for record in coerced):
        raise UngroundedRelationshipError(
            "AI-generated, derived, or legacy-import provenance alone cannot authorize a canonical cross-model relation"
        )
    return tuple(coerced)


def _registry_entry(logicguard: Any, snapshot: Any) -> Any:
    return logicguard.ModelRegistryEntry(
        model_ref=logicguard.QualifiedModelRef(snapshot.model_id, snapshot.revision),
        content_digest=snapshot.content_digest,
        snapshot_artifact_schema=snapshot.artifact_schema,
        store_schema_version=snapshot.store_schema_version,
    )


def commit_scope_mesh(
    repo_root: Path,
    *,
    authority_scope: str,
    model_bindings: Sequence[LogicGuardBinding],
    expected_revision: str | None,
    idempotency_key: str,
    actor: str,
    relations: Sequence[GroundedModelRelation] = (),
    memberships: Sequence[GroundedMembership] = (),
    unresolved_relationships: Sequence[Mapping[str, Any]] = (),
) -> MeshCommitResult:
    logicguard = _researchguard_logic_module()
    scope = normalize_authority_scope(authority_scope)
    if not model_bindings:
        raise ValueError("A scope mesh requires at least one exact model binding")
    unique: dict[tuple[str, str], LogicGuardBinding] = {}
    model_store, _idempotency_keys = open_pinned_model_read_store(repo_root, scope)
    snapshots: dict[tuple[str, str], Any] = {}
    for binding in model_bindings:
        if normalize_authority_scope(binding.authority_scope) != scope:
            raise AuthorityScopeError("ModelMesh cannot pin a model from another authority scope")
        key = (binding.model_id, binding.revision_id)
        unique[key] = binding
        snapshot = read_exact_model(repo_root, binding, model_store=model_store)
        snapshots[key] = snapshot
    registry = tuple(
        _registry_entry(logicguard, snapshots[key])
        for key in sorted(snapshots)
    )

    cross_edges: list[Any] = []
    for relation in relations:
        if relation.source.authority_scope != scope or relation.target.authority_scope != scope:
            raise AuthorityScopeError("Cross-model edge cannot cross public/private/candidate stores")
        if (relation.source.model_id, relation.source.revision_id) not in snapshots:
            raise ExactBindingError("Cross-model relation source is not pinned by this mesh")
        if (relation.target.model_id, relation.target.revision_id) not in snapshots:
            raise ExactBindingError("Cross-model relation target is not pinned by this mesh")
        cross_edges.append(
            logicguard.CrossModelEdge(
                id=relation.relation_id,
                source=_qualified_node_ref(logicguard, relation.source),
                target=_qualified_node_ref(logicguard, relation.target),
                type=relation.edge_type,
                weight=relation.weight,
                explanation=relation.explanation,
                source_block_id=relation.source.block_id,
                target_block_id=relation.target.block_id,
                provenance=_grounding_records(relation.provenance),
                metadata=dict(relation.metadata),
            )
        )

    mesh_memberships: list[Any] = []
    for membership in memberships:
        if membership.owner.authority_scope != scope or membership.logical_model.authority_scope != scope:
            raise AuthorityScopeError("ModelMesh membership cannot cross authority scopes")
        if (membership.owner.model_id, membership.owner.revision_id) not in snapshots:
            raise ExactBindingError("Membership owner is not pinned by this mesh")
        if (membership.logical_model.model_id, membership.logical_model.revision_id) not in snapshots:
            raise ExactBindingError("Membership logical model is not pinned by this mesh")
        mesh_memberships.append(
            logicguard.MeshMembership(
                owner=_qualified_node_ref(logicguard, membership.owner),
                logical_model=_qualified_model_ref(logicguard, membership.logical_model),
                roles=tuple(membership.roles),
                role_metadata=dict(membership.role_metadata),
                provenance=_grounding_records(membership.provenance),
            )
        )

    mesh_id = mesh_id_for_scope(scope)
    mesh_store = logicguard.FileModelMeshStore(mesh_store_root(repo_root, scope), model_store=model_store)
    baseline = None
    expected_catalog_revision = None
    if expected_revision is not None:
        current = mesh_store.get(mesh_id, expected_revision)
        baseline = mesh_store.current_catalog_pin(current.mesh_id, current.revision)
        expected_catalog_revision = baseline.catalog_revision
    definition = logicguard.ModelMeshDefinition(
        mesh_id=mesh_id,
        registry=registry,
        memberships=tuple(mesh_memberships),
        cross_model_edges=tuple(cross_edges),
        invalidation_baseline=baseline,
        provenance=(
            _provenance_record(
                origin_kind="derived",
                content={"scope": scope, "model_pins": [str(item.model_ref) for item in registry]},
                source_id=f"khaos-brain:{scope}:sleep-model-mesh",
                source_reference="local_kb.model_maintenance",
                actor=actor,
            ),
        ),
        metadata={
            "authority_schema": LOGICGUARD_AUTHORITY_SCHEMA,
            "authority_scope": scope,
            "unresolved_relationships": [dict(item) for item in unresolved_relationships],
            "created_by_owner": actor,
        },
    )
    transaction = mesh_store.begin(
        mesh_id,
        expected_revision,
        idempotency_key,
        actor,
        expected_overlay_catalog_revision=expected_catalog_revision,
    )
    transaction.stage(definition)
    receipt = transaction.commit()
    bound = tuple(
        LogicGuardBinding(
            authority_scope=scope,
            model_id=binding.model_id,
            node_id=binding.node_id,
            block_id=binding.block_id,
            revision_id=binding.revision_id,
            mesh_id=mesh_id,
            mesh_revision_id=str(receipt.revision),
        )
        for binding in unique.values()
    )
    return MeshCommitResult(
        mesh_id=mesh_id,
        mesh_revision_id=str(receipt.revision),
        content_digest=str(receipt.content_digest),
        receipt=receipt.to_dict(),
        bindings=bound,
        unresolved_relationships=tuple(dict(item) for item in unresolved_relationships),
    )


def read_exact_mesh(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    mesh_store: Any | None = None,
) -> Any:
    if not binding.mesh_id or not binding.mesh_revision_id:
        raise ExactBindingError("Exact mesh id and revision are required")
    store = mesh_store or open_mesh_store(repo_root, binding.authority_scope)
    try:
        snapshot = store.get(binding.mesh_id, binding.mesh_revision_id)
    except Exception as exc:
        raise ExactBindingError(
            f"Exact LogicGuard mesh is unavailable for {binding.mesh_id}@{binding.mesh_revision_id}: {exc}"
        ) from exc
    return _validate_exact_mesh_snapshot(binding, snapshot)


def _validate_exact_mesh_snapshot(binding: LogicGuardBinding, snapshot: Any) -> Any:
    if (
        str(snapshot.mesh_id) != binding.mesh_id
        or str(snapshot.revision) != binding.mesh_revision_id
    ):
        raise ExactBindingError(
            "Exact LogicGuard mesh snapshot does not match the bound revision"
        )
    pinned = {
        (str(item.model_ref.model_id), str(item.model_ref.revision))
        for item in snapshot.registry
    }
    if (binding.model_id, binding.revision_id) not in pinned:
        raise ExactBindingError("Bound card model revision is not pinned by the exact mesh revision")
    if str(snapshot.metadata.get("authority_scope") or "") != normalize_authority_scope(binding.authority_scope):
        raise AuthorityScopeError("Exact mesh metadata crosses the requested authority scope")
    return snapshot


def materialize_bound_neighborhood(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    hop_limit: int = 3,
    node_limit: int = 80,
    edge_limit: int = 160,
    model_limit: int = 20,
    byte_limit: int = 2_000_000,
    evaluate: bool = True,
    model_store: Any | None = None,
    mesh_store: Any | None = None,
    model_snapshot: Any | None = None,
    mesh_view: Any | None = None,
) -> ModelNeighborhood:
    logicguard = _researchguard_logic_module()
    current_model_store = model_store or open_model_store(
        repo_root, binding.authority_scope
    )
    if model_snapshot is None:
        read_exact_model(repo_root, binding, model_store=current_model_store)
    else:
        model = model_snapshot.to_model()
        if (
            str(model_snapshot.model_id) != binding.model_id
            or str(model_snapshot.revision) != binding.revision_id
            or str(model.metadata.get("authority_scope") or "")
            != normalize_authority_scope(binding.authority_scope)
            or binding.node_id not in model.nodes
            or binding.block_id not in model.blocks
        ):
            raise ExactBindingError(
                "Exact LogicGuard model snapshot does not match the bound context"
            )
    if mesh_view is None:
        store = mesh_store or open_mesh_store(
            repo_root,
            binding.authority_scope,
            model_store=current_model_store,
        )
        read_exact_mesh(repo_root, binding, mesh_store=store)
        view = store.open_view(binding.mesh_id, binding.mesh_revision_id)
    else:
        view = mesh_view
        _validate_exact_mesh_snapshot(binding, view.snapshot)
    root = _qualified_node_ref(logicguard, binding)
    request = logicguard.MeshMaterializationRequest(
        roots=(root,),
        direction="both",
        hop_limit=max(0, int(hop_limit)),
        node_limit=max(1, int(node_limit)),
        edge_limit=max(0, int(edge_limit)),
        model_limit=max(1, int(model_limit)),
        byte_limit=max(1024, int(byte_limit)),
        profile="bounded",
    )
    materialized = logicguard.materialize_mesh(view, request)
    evaluation_payload: Mapping[str, Any] = {}
    if evaluate:
        evaluation = logicguard.evaluate_materialized_mesh(
            view,
            materialized,
            requested_claim_scope=(root,),
            profile="bounded",
            depth_budget=max(1, int(hop_limit)),
            authority="production",
        )
        evaluation_payload = evaluation.to_dict()
    return ModelNeighborhood(
        binding=binding,
        materialized=materialized.to_dict(),
        evaluation=evaluation_payload,
    )


def _build_bound_argument_context(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    authority_pointer_digest: str,
    hop_limit: int = 1,
    node_limit: int = 80,
    edge_limit: int = 160,
    model_limit: int = 20,
    byte_limit: int = 2_000_000,
) -> dict[str, Any]:
    """Build one exact context after the current-generation gate has passed."""

    resolved_root = str(Path(repo_root).resolve())
    model_store, _mesh_store = _cached_bound_read_session(
        resolved_root,
        authority_pointer_digest,
        binding.authority_scope,
    )
    mesh_view = _cached_current_mesh_view(
        resolved_root,
        authority_pointer_digest,
        binding.authority_scope,
        binding.mesh_id,
        binding.mesh_revision_id,
    )
    snapshot = read_exact_model(repo_root, binding, model_store=model_store)
    mesh = _validate_exact_mesh_snapshot(binding, mesh_view.snapshot)
    model = snapshot.to_model()
    block = model.blocks[binding.block_id]
    member_ids = {str(item) for item in block.member_nodes}
    member_ids.add(binding.node_id)
    nodes = [
        model.nodes[node_id].to_dict()
        for node_id in sorted(member_ids)
        if node_id in model.nodes
    ]
    edges = [
        edge.to_dict()
        for edge in model.edges
        if str(edge.source) in member_ids and str(edge.target) in member_ids
    ]
    neighborhood = materialize_bound_neighborhood(
        repo_root,
        binding,
        hop_limit=hop_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        model_limit=model_limit,
        byte_limit=byte_limit,
        evaluate=True,
        model_store=model_store,
        model_snapshot=snapshot,
        mesh_view=mesh_view,
    )
    materialized = dict(neighborhood.materialized)
    return {
        "binding": binding.to_dict(),
        "model_content_digest": str(snapshot.content_digest),
        "mesh_content_digest": str(mesh.content_digest),
        "root_claim": binding.node_id,
        "argument_block": block.to_dict(),
        "nodes": nodes,
        "edges": edges,
        "open_role_gaps": normalize_string_list(model.metadata.get("open_role_gaps")),
        "neighborhood": {
            "model_pins": list(materialized.get("model_pins") or []),
            "cross_edges": list(materialized.get("cross_edges") or []),
            "memberships": list(materialized.get("memberships") or []),
            "frontier": list(materialized.get("frontier") or []),
            "complete": bool(materialized.get("complete")),
            "truncation_reasons": list(materialized.get("truncation_reasons") or []),
            "materialization_fingerprint": str(
                materialized.get("materialization_fingerprint") or ""
            ),
        },
        "evaluation": dict(neighborhood.evaluation),
        "claim_boundary": (
            "This is an exact LogicGuard argument and bounded ModelMesh read. "
            "It licenses structural reasoning only and does not establish factual truth."
        ),
    }


@lru_cache(maxsize=256)
def _cached_bound_argument_context_json(
    repo_root: str,
    authority_pointer_digest: str,
    authority_scope: str,
    model_id: str,
    node_id: str,
    block_id: str,
    revision_id: str,
    mesh_id: str,
    mesh_revision_id: str,
    hop_limit: int,
    node_limit: int,
    edge_limit: int,
    model_limit: int,
    byte_limit: int,
) -> str:
    # ``authority_pointer_digest`` intentionally participates in the cache key.
    # LogicGuard revisions and mesh revisions are immutable; a Sleep publication
    # changes the sole current pointer digest and therefore cannot reuse an old
    # generation's context.  Cache JSON rather than a mutable dictionary so one
    # caller can never alter a later caller's reasoning context.
    context = _build_bound_argument_context(
        Path(repo_root),
        LogicGuardBinding(
            authority_scope=authority_scope,
            model_id=model_id,
            node_id=node_id,
            block_id=block_id,
            revision_id=revision_id,
            mesh_id=mesh_id,
            mesh_revision_id=mesh_revision_id,
        ),
        authority_pointer_digest=authority_pointer_digest,
        hop_limit=hop_limit,
        node_limit=node_limit,
        edge_limit=edge_limit,
        model_limit=model_limit,
        byte_limit=byte_limit,
    )
    return json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_bound_argument_context(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    hop_limit: int = 1,
    node_limit: int = 80,
    edge_limit: int = 160,
    model_limit: int = 20,
    byte_limit: int = 2_000_000,
) -> dict[str, Any]:
    """Read one exact card argument plus its bounded, grounded mesh neighborhood.

    Successful immutable reads are cached only inside the current process and
    only for the exact current authority generation.  Missing or stale current
    authority remains a visible error; there is no alternate model reader.
    """

    root = Path(repo_root).resolve()
    generation = load_authority_generation(root)
    scope = normalize_authority_scope(binding.authority_scope)
    scope_mesh = generation.get("scope_meshes", {}).get(scope, {})
    if (
        binding.mesh_id != str(scope_mesh.get("mesh_id") or "")
        or binding.mesh_revision_id != str(scope_mesh.get("mesh_revision_id") or "")
    ):
        raise ExactBindingError(
            "Bound LogicGuard context is outside the sole current authority generation"
        )
    cached = _cached_bound_argument_context_json(
        str(root),
        str(generation.get("pointer_digest") or ""),
        scope,
        binding.model_id,
        binding.node_id,
        binding.block_id,
        binding.revision_id,
        binding.mesh_id,
        binding.mesh_revision_id,
        max(0, int(hop_limit)),
        max(1, int(node_limit)),
        max(0, int(edge_limit)),
        max(1, int(model_limit)),
        max(1024, int(byte_limit)),
    )
    return json.loads(cached)


def simulate_bound_mesh(
    repo_root: Path,
    binding: LogicGuardBinding,
    delta: Any,
    *,
    hop_limit: int = 3,
    node_limit: int = 80,
    edge_limit: int = 160,
    model_limit: int = 20,
    byte_limit: int = 2_000_000,
) -> Any:
    logicguard = _researchguard_logic_module()
    snapshot = read_exact_mesh(repo_root, binding)
    if str(delta.base_mesh_id) != str(snapshot.mesh_id) or str(delta.base_mesh_revision) != str(snapshot.revision):
        raise ExactBindingError("Dream simulation delta does not pin the bound exact mesh revision")
    store = open_mesh_store(repo_root, binding.authority_scope)
    root = _qualified_node_ref(logicguard, binding)
    request = logicguard.MeshMaterializationRequest(
        roots=(root,),
        direction="both",
        hop_limit=max(0, int(hop_limit)),
        node_limit=max(1, int(node_limit)),
        edge_limit=max(0, int(edge_limit)),
        model_limit=max(1, int(model_limit)),
        byte_limit=max(1024, int(byte_limit)),
        profile="bounded",
    )
    return logicguard.simulate_mesh(
        store.open_view(binding.mesh_id, binding.mesh_revision_id),
        delta,
        request,
        requested_claim_scope=(root,),
        profile="bounded",
        depth_budget=max(1, int(hop_limit)),
    )


def scope_authority_status(repo_root: Path, scope: str) -> dict[str, Any]:
    normalized = normalize_authority_scope(scope)
    preflight = researchguard_logic_dependency_preflight(strict=False)
    if not preflight["ok"]:
        return {"ok": False, "scope": normalized, "issues": list(preflight["issues"])}
    issues: list[str] = []
    try:
        model_store = open_model_store(repo_root, normalized)
        mesh_store = open_mesh_store(repo_root, normalized)
        model_recoveries = model_store.recover()
        mesh_recoveries = mesh_store.recover()
        model_ids = tuple(str(item) for item in model_store.list_models())
        mesh_ids = tuple(str(item) for item in mesh_store.list_meshes())
    except Exception as exc:
        issues.append(f"{type(exc).__name__}: {exc}")
        model_recoveries = ()
        mesh_recoveries = ()
        model_ids = ()
        mesh_ids = ()
    return {
        "ok": not issues,
        "scope": normalized,
        "model_store_root": str(model_store_root(repo_root, normalized)),
        "mesh_store_root": str(mesh_store_root(repo_root, normalized)),
        "model_ids": list(model_ids),
        "mesh_ids": list(mesh_ids),
        "model_recovery_receipts": [item.to_dict() for item in model_recoveries],
        "mesh_recovery_receipts": [item.to_dict() for item in mesh_recoveries],
        "issues": issues,
    }
