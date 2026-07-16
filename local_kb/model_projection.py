from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import yaml

from local_kb.common import normalize_string_list, normalize_text
from local_kb.logicguard_models import (
    ExactBindingError,
    LogicGuardBinding,
    json_safe,
    open_mesh_store,
    normalize_authority_scope,
    open_pinned_model_read_store,
    read_exact_mesh,
    read_exact_model,
)


CARD_PROJECTION_SCHEMA_VERSION = "khaos-brain.card-projection.v1"
PROJECTION_BINDING_FIELDS = (
    "authority_generation_id",
    "authority_scope",
    "logicguard_model_id",
    "logicguard_node_id",
    "logicguard_block_id",
    "logicguard_revision_id",
    "logicguard_mesh_id",
    "logicguard_mesh_revision_id",
)


class ProjectionValidationError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def projection_digest(value: Mapping[str, Any]) -> str:
    unsigned = {key: json_safe(item) for key, item in value.items() if key != "projection_digest"}
    return "sha256:" + hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()


def binding_from_projection(value: Mapping[str, Any]) -> LogicGuardBinding:
    if str(value.get("projection_schema_version") or "") != CARD_PROJECTION_SCHEMA_VERSION:
        raise ProjectionValidationError("Card projection schema is missing or unsupported")
    missing = [field for field in PROJECTION_BINDING_FIELDS if not str(value.get(field) or "").strip()]
    if missing:
        raise ProjectionValidationError("Card projection lacks exact LogicGuard binding fields: " + ", ".join(missing))
    try:
        scope = normalize_authority_scope(str(value.get("authority_scope") or ""))
    except ValueError as exc:
        raise ProjectionValidationError(str(exc)) from exc
    return LogicGuardBinding(
        authority_scope=scope,
        model_id=str(value["logicguard_model_id"]),
        node_id=str(value["logicguard_node_id"]),
        block_id=str(value["logicguard_block_id"]),
        revision_id=str(value["logicguard_revision_id"]),
        mesh_id=str(value["logicguard_mesh_id"]),
        mesh_revision_id=str(value["logicguard_mesh_revision_id"]),
    )


def _node_by_projection_role(model: Any, role: str) -> Any | None:
    for node in model.nodes.values():
        if str(node.metadata.get("projection_role") or "") == role:
            return node
    return None


def _related_refs_by_model(mesh: Any) -> dict[tuple[str, str], set[tuple[str, str]]]:
    related: dict[tuple[str, str], set[tuple[str, str]]] = {}

    def connect(left: tuple[str, str], right: tuple[str, str]) -> None:
        if left == right:
            return
        related.setdefault(left, set()).add(right)
        related.setdefault(right, set()).add(left)

    for edge in mesh.cross_model_edges:
        source_key = (str(edge.source.model_id), str(edge.source.revision))
        target_key = (str(edge.target.model_id), str(edge.target.revision))
        connect(source_key, target_key)
    for membership in mesh.memberships:
        owner_key = (str(membership.owner.model_id), str(membership.owner.revision))
        logical_key = (
            str(membership.logical_model.model_id),
            str(membership.logical_model.revision),
        )
        connect(owner_key, logical_key)
    return related


def _related_card_ids_by_model(mesh: Any, model_store: Any) -> dict[tuple[str, str], list[str]]:
    related_refs = _related_refs_by_model(mesh)
    referenced = sorted({item for values in related_refs.values() for item in values})
    card_id_by_ref: dict[tuple[str, str], str] = {}
    for model_id, revision_id in referenced:
        snapshot = model_store.get(model_id, revision_id)
        card_id = str(snapshot.to_model().metadata.get("card_id") or "")
        if card_id:
            card_id_by_ref[(model_id, revision_id)] = card_id
    return {
        source: sorted(
            {
                card_id_by_ref[target]
                for target in targets
                if target in card_id_by_ref
            }
        )
        for source, targets in related_refs.items()
    }


def _project_card_from_exact_snapshots(
    binding: LogicGuardBinding,
    *,
    authority_generation_id: str,
    snapshot: Any,
    mesh: Any,
    related_card_ids: Sequence[str],
) -> dict[str, Any]:
    if not str(authority_generation_id or "").strip():
        raise ProjectionValidationError("Projection requires an exact authority generation id")
    model = snapshot.to_model()
    if model.root_claim != binding.node_id:
        raise ProjectionValidationError("Bound node is not the model root claim")
    block = model.blocks.get(binding.block_id)
    if block is None or block.root_claim != binding.node_id:
        raise ProjectionValidationError("Bound ArgumentBlock does not own the bound root claim")
    metadata = model.metadata
    if str(metadata.get("authority_scope") or "") != binding.authority_scope:
        raise ProjectionValidationError("Model authority scope differs from the projection binding")
    if str(mesh.metadata.get("authority_scope") or "") != binding.authority_scope:
        raise ProjectionValidationError("Mesh authority scope differs from the projection binding")

    context = _node_by_projection_role(model, "applicability_context")
    action = _node_by_projection_role(model, "action_under_consideration")
    claim = model.nodes[binding.node_id]
    alternatives = metadata.get("alternatives", [])
    if not isinstance(alternatives, list):
        alternatives = []
    extensions = metadata.get("projection_extensions")
    projection: dict[str, Any] = (
        json_safe(dict(extensions))
        if isinstance(extensions, Mapping)
        else {}
    )
    projection.update({
        "projection_schema_version": CARD_PROJECTION_SCHEMA_VERSION,
        "authority_generation_id": str(authority_generation_id),
        "authority_scope": binding.authority_scope,
        "logicguard_model_id": binding.model_id,
        "logicguard_node_id": binding.node_id,
        "logicguard_block_id": binding.block_id,
        "logicguard_revision_id": binding.revision_id,
        "logicguard_mesh_id": binding.mesh_id,
        "logicguard_mesh_revision_id": binding.mesh_revision_id,
        "id": str(metadata.get("card_id") or ""),
        "title": str(model.title or metadata.get("card_id") or ""),
        "type": str(metadata.get("card_type") or "model"),
        "scope": str(metadata.get("declared_scope") or "public"),
        "domain_path": normalize_string_list(metadata.get("domain_path")),
        "cross_index": normalize_string_list(metadata.get("cross_index")),
        "related_cards": sorted({str(item) for item in related_card_ids if str(item)}),
        "tags": normalize_string_list(metadata.get("tags")),
        "trigger_keywords": normalize_string_list(metadata.get("trigger_keywords")),
        "if": {"notes": normalize_text(context.text if context is not None else "")},
        "action": {"description": normalize_text(action.text if action is not None else "")},
        "predict": {
            "expected_result": normalize_text(claim.text),
            "alternatives": [
                {
                    "when": normalize_text(item.get("when")),
                    "result": normalize_text(item.get("result")),
                }
                for item in alternatives
                if isinstance(item, Mapping) and normalize_text(item.get("result")).strip()
            ],
        },
        "use": {"guidance": normalize_text(metadata.get("operational_guidance"))},
        "confidence": float(metadata.get("confidence") or claim.confidence),
        "source": json_safe(metadata.get("display_source") or []),
        "status": str(metadata.get("status") or "candidate"),
        "updated_at": str(metadata.get("updated_at") or ""),
        "logicguard_open_role_gaps": normalize_string_list(metadata.get("open_role_gaps")),
    })
    structured_extensions = metadata.get("structured_extension_fields")
    if isinstance(structured_extensions, Mapping):
        for block_name in ("if", "action", "predict", "use"):
            block_extensions = structured_extensions.get(block_name)
            if isinstance(block_extensions, Mapping):
                projection[block_name].update(json_safe(dict(block_extensions)))
    i18n = metadata.get("i18n")
    if isinstance(i18n, Mapping) and i18n:
        projection["i18n"] = json_safe(i18n)
    if not projection["id"]:
        raise ProjectionValidationError("Canonical model metadata has no card id")
    projection["projection_digest"] = projection_digest(projection)
    return projection


def project_card(
    repo_root: Path,
    binding: LogicGuardBinding,
    *,
    authority_generation_id: str,
) -> dict[str, Any]:
    model_store, _idempotency_keys = open_pinned_model_read_store(
        repo_root,
        binding.authority_scope,
    )
    snapshot = read_exact_model(repo_root, binding, model_store=model_store)
    mesh_store = open_mesh_store(
        repo_root,
        binding.authority_scope,
        model_store=model_store,
    )
    mesh = read_exact_mesh(repo_root, binding, mesh_store=mesh_store)
    related = _related_card_ids_by_model(mesh, model_store)
    return _project_card_from_exact_snapshots(
        binding,
        authority_generation_id=authority_generation_id,
        snapshot=snapshot,
        mesh=mesh,
        related_card_ids=related.get((binding.model_id, binding.revision_id), ()),
    )


def project_cards(
    repo_root: Path,
    bindings: Sequence[LogicGuardBinding],
    *,
    authority_generation_id: str,
) -> list[dict[str, Any]]:
    """Project one exact scope/mesh cohort with a single pinned store read."""

    if not bindings:
        return []
    first = bindings[0]
    cohort = (
        first.authority_scope,
        first.mesh_id,
        first.mesh_revision_id,
    )
    for binding in bindings:
        if (
            binding.authority_scope,
            binding.mesh_id,
            binding.mesh_revision_id,
        ) != cohort:
            raise ProjectionValidationError(
                "Batch projection requires one exact authority scope and mesh revision"
            )
    model_store, _idempotency_keys = open_pinned_model_read_store(
        repo_root,
        first.authority_scope,
    )
    mesh_store = open_mesh_store(
        repo_root,
        first.authority_scope,
        model_store=model_store,
    )
    mesh = read_exact_mesh(repo_root, first, mesh_store=mesh_store)
    related = _related_card_ids_by_model(mesh, model_store)
    projected: list[dict[str, Any]] = []
    for binding in bindings:
        snapshot = read_exact_model(repo_root, binding, model_store=model_store)
        projected.append(
            _project_card_from_exact_snapshots(
                binding,
                authority_generation_id=authority_generation_id,
                snapshot=snapshot,
                mesh=mesh,
                related_card_ids=related.get((binding.model_id, binding.revision_id), ()),
            )
        )
    return projected


def validate_card_projection(
    repo_root: Path,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    binding = binding_from_projection(projection)
    stored_digest = str(projection.get("projection_digest") or "")
    if not stored_digest:
        raise ProjectionValidationError("Card projection has no projection digest")
    calculated = projection_digest(projection)
    if stored_digest != calculated:
        raise ProjectionValidationError("Card projection digest mismatch")
    try:
        expected = project_card(
            repo_root,
            binding,
            authority_generation_id=str(projection.get("authority_generation_id") or ""),
        )
    except (ExactBindingError, ValueError, KeyError) as exc:
        raise ProjectionValidationError(str(exc)) from exc
    actual = json_safe(dict(projection))
    if actual != expected:
        keys = sorted(
            key
            for key in set(actual) | set(expected)
            if actual.get(key) != expected.get(key)
        )
        raise ProjectionValidationError(
            "Card projection differs from its canonical LogicGuard model: " + ", ".join(keys)
        )
    return {
        "ok": True,
        "projection_digest": stored_digest,
        "binding": binding.to_dict(),
        "card_id": str(projection.get("id") or ""),
    }


def validate_card_projections(
    repo_root: Path,
    projections: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Validate exact projections in scope/mesh cohorts without repeated scans."""

    bindings: list[LogicGuardBinding] = []
    groups: dict[tuple[str, str, str, str], list[int]] = {}
    for index, projection in enumerate(projections):
        binding = binding_from_projection(projection)
        stored_digest = str(projection.get("projection_digest") or "")
        if not stored_digest:
            raise ProjectionValidationError(
                f"Card projection {projection.get('id') or index} has no projection digest"
            )
        if stored_digest != projection_digest(projection):
            raise ProjectionValidationError(
                f"Card projection {projection.get('id') or index} digest mismatch"
            )
        generation_id = str(projection.get("authority_generation_id") or "")
        key = (
            binding.authority_scope,
            binding.mesh_id,
            binding.mesh_revision_id,
            generation_id,
        )
        groups.setdefault(key, []).append(index)
        bindings.append(binding)

    results: list[dict[str, Any] | None] = [None] * len(projections)
    for (_scope, _mesh_id, _mesh_revision_id, generation_id), indexes in groups.items():
        expected_rows = project_cards(
            repo_root,
            [bindings[index] for index in indexes],
            authority_generation_id=generation_id,
        )
        for index, expected in zip(indexes, expected_rows, strict=True):
            projection = projections[index]
            actual = json_safe(dict(projection))
            if actual != expected:
                keys = sorted(
                    key
                    for key in set(actual) | set(expected)
                    if actual.get(key) != expected.get(key)
                )
                raise ProjectionValidationError(
                    "Card projection "
                    f"{projection.get('id') or index} differs from its canonical "
                    "LogicGuard model: "
                    + ", ".join(keys)
                )
            results[index] = {
                "ok": True,
                "projection_digest": str(projection.get("projection_digest") or ""),
                "binding": bindings[index].to_dict(),
                "card_id": str(projection.get("id") or ""),
            }
    return [dict(item) for item in results if item is not None]


def projection_scope_for_path(repo_root: Path, path: Path) -> str:
    resolved_root = Path(repo_root).resolve()
    resolved = Path(path).resolve()
    for scope in ("public", "private", "candidates"):
        try:
            resolved.relative_to(resolved_root / "kb" / scope)
        except ValueError:
            continue
        return scope
    raise ProjectionValidationError("Projection path is outside public/private/candidates KB roots")


def validate_projection_path_scope(repo_root: Path, path: Path, projection: Mapping[str, Any]) -> str:
    path_scope = projection_scope_for_path(repo_root, path)
    binding = binding_from_projection(projection)
    if path_scope != binding.authority_scope:
        raise ProjectionValidationError(
            f"Projection path scope {path_scope} differs from authority scope {binding.authority_scope}"
        )
    if path_scope == "private" and str(projection.get("scope") or "") != "private":
        raise ProjectionValidationError("Private authority projection must remain declared private")
    return path_scope


def write_card_projection_atomic(
    repo_root: Path,
    path: Path,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    validate_card_projection(repo_root, projection)
    validate_projection_path_scope(repo_root, path, projection)
    return _write_card_projection_atomic(path, projection)


def _write_card_projection_atomic(
    path: Path,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(json_safe(dict(projection)), handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return {
        "ok": True,
        "path": str(path),
        "card_id": str(projection.get("id") or ""),
        "projection_digest": str(projection.get("projection_digest") or ""),
    }


def write_card_projections_atomic(
    repo_root: Path,
    items: Sequence[tuple[Path, Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Validate one exact batch, then atomically replace each YAML projection."""

    projections = [projection for _path, projection in items]
    validate_card_projections(repo_root, projections)
    for path, projection in items:
        validate_projection_path_scope(repo_root, path, projection)
    return [
        _write_card_projection_atomic(path, projection)
        for path, projection in items
    ]


def load_card_projection(repo_root: Path, path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ProjectionValidationError(f"Card projection cannot be loaded: {exc}") from exc
    if not isinstance(value, Mapping):
        raise ProjectionValidationError("Card projection is not an object")
    projection = json_safe(dict(value))
    validate_projection_path_scope(repo_root, path, projection)
    validate_card_projection(repo_root, projection)
    return projection


def active_index_binding_record(projection: Mapping[str, Any]) -> dict[str, str]:
    binding = binding_from_projection(projection)
    return {
        "authority_generation_id": str(projection.get("authority_generation_id") or ""),
        "authority_scope": binding.authority_scope,
        "logicguard_model_id": binding.model_id,
        "logicguard_node_id": binding.node_id,
        "logicguard_block_id": binding.block_id,
        "logicguard_revision_id": binding.revision_id,
        "logicguard_mesh_id": binding.mesh_id,
        "logicguard_mesh_revision_id": binding.mesh_revision_id,
        "projection_digest": str(projection.get("projection_digest") or ""),
    }
