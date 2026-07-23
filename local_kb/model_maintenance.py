from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from local_kb.active_index import rebuild_active_index, validate_active_index
from local_kb.common import utc_now_iso
from local_kb.logicguard_models import (
    AUTHORITY_SCOPES,
    ExactBindingError,
    GroundedMembership,
    GroundedModelRelation,
    LogicGuardBinding,
    authority_generation_pointer_path,
    authority_root,
    build_authority_generation_payload,
    canonical_digest,
    commit_card_model,
    commit_scope_mesh,
    load_authority_generation,
    mesh_id_for_scope,
    open_mesh_store,
    open_model_store,
    publish_authority_generation,
    read_exact_mesh,
    recover_authority_scopes,
)
from local_kb.model_projection import (
    binding_from_projection,
    project_cards,
    projection_digest,
    projection_scope_for_path,
    validate_card_projections,
    validate_projection_path_scope,
    write_card_projections_atomic,
)
from local_kb.models import Entry
from local_kb.store import build_local_entry_source, load_yaml_file


SLEEP_AUTHORITY_WRITER = "local_kb.lifecycle.run_incremental_sleep"
MODEL_GENERATION_RECEIPT_SCHEMA = "khaos-brain.sleep-model-generation.v1"
CARD_SCOPES = ("public", "private", "candidates")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(_json_safe(dict(payload)), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _card_paths(repo_root: Path) -> Iterable[tuple[str, Path]]:
    for scope in CARD_SCOPES:
        base = Path(repo_root) / "kb" / scope
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.yaml")):
            yield scope, path


def _relative_card_path(repo_root: Path, value: str | Path) -> tuple[str, str, Path]:
    root = Path(repo_root).resolve()
    path = Path(value)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    scope = projection_scope_for_path(root, resolved)
    relative = resolved.relative_to(root).as_posix()
    return scope, relative, resolved


def _snapshot_active_authority(repo_root: Path, operation_id: str) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    tx_root = root / ".local" / "kbtx" / canonical_digest(operation_id)[:12]
    rollback = tx_root / "r"
    if tx_root.exists():
        shutil.rmtree(tx_root)
    sources = (
        root / "kb" / "public",
        root / "kb" / "private",
        root / "kb" / "candidates",
        root / "kb" / "indexes",
        authority_root(root),
    )
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        relative = source.relative_to(root)
        destination = rollback / f"s{index}"
        existed = source.exists()
        if existed:
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        rows.append(
            {
                "path": relative.as_posix(),
                "backup": destination.relative_to(root).as_posix() if existed else "",
                "existed": existed,
            }
        )
    return {"operation_id": operation_id, "transaction_root": tx_root.relative_to(root).as_posix(), "rows": rows}


def _restore_active_authority(repo_root: Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    restored: list[str] = []
    removed: list[str] = []
    for row in snapshot.get("rows", []):
        if not isinstance(row, Mapping):
            continue
        relative = Path(str(row.get("path") or ""))
        target = (root / relative).resolve()
        target.relative_to(root)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if not bool(row.get("existed")):
            removed.append(relative.as_posix())
            continue
        source = (root / str(row.get("backup") or "")).resolve()
        source.relative_to(root)
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise RuntimeError(f"Model-generation rollback backup is missing: {source}")
        restored.append(relative.as_posix())
    return {"ok": True, "restored": restored, "removed_new": removed}


def _cleanup_snapshot(repo_root: Path, snapshot: Mapping[str, Any]) -> None:
    root = Path(repo_root).resolve()
    path = (root / str(snapshot.get("transaction_root") or "")).resolve()
    path.relative_to(root / ".local" / "kbtx")
    if path.exists():
        shutil.rmtree(path)


def _current_projection_rows(
    repo_root: Path,
    *,
    replacing_paths: Sequence[str] = (),
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    root = Path(repo_root).resolve()
    paths = list(_card_paths(root))
    replacing = {str(item).replace("\\", "/") for item in replacing_paths}
    try:
        generation = load_authority_generation(root)
    except ExactBindingError:
        if paths:
            raise RuntimeError(
                "Current LogicGuard authority is missing while card files exist; run the versioned upgrade"
            )
        generation = build_authority_generation_payload(
            generation_id="generation-empty-bootstrap",
            scope_meshes={},
            projection_manifest_digest="sha256:" + canonical_digest([]),
            projection_count=0,
            actor=SLEEP_AUTHORITY_WRITER,
        )
    rows: dict[str, dict[str, Any]] = {}
    projections: list[dict[str, Any]] = []
    for scope, path in paths:
        relative = path.relative_to(root).as_posix()
        # A Sleep-owned explicit upsert is the direct-to-current disposition
        # for this exact path.  Exclude only that named old/raw byte surface
        # from the current projection read, then rebuild it through LogicGuard
        # in the same atomic generation.  Unnamed residuals still fail below.
        if relative in replacing:
            continue
        projection = load_yaml_file(path)
        validate_projection_path_scope(root, path, projection)
        if str(projection.get("authority_generation_id") or "") != str(generation.get("generation_id") or ""):
            raise RuntimeError(f"Projection {path} is outside the current authority generation")
        rows[relative] = {
            "scope": scope,
            "path": relative,
            "card_id": str(projection.get("id") or ""),
            "projection": projection,
            "binding": binding_from_projection(projection),
        }
        projections.append(projection)
    # Deep validation must retain exact model/mesh checks without reopening the
    # same scoped mesh for every card.  The batch validator pins one store and
    # one mesh revision per cohort, then verifies every canonical projection.
    validate_card_projections(root, projections)
    return generation, rows


def load_current_model_entries(repo_root: Path) -> tuple[list[Entry], dict[str, Any]]:
    """Load the generation-bound catalog without replaying every model revision.

    The authority pointer binds the complete projection manifest.  Catalog
    reads therefore verify each projection digest, exact binding, path scope,
    generation id, scoped mesh revision, and the aggregate manifest.  A detail
    or reasoning read still opens the exact immutable model/mesh revision.
    """

    root = Path(repo_root).resolve()
    generation = load_authority_generation(root)
    rows: dict[str, dict[str, Any]] = {}
    manifest_rows: list[dict[str, Any]] = []
    for scope, path in _card_paths(root):
        projection = load_yaml_file(path)
        validate_projection_path_scope(root, path, projection)
        stored_projection_digest = str(projection.get("projection_digest") or "")
        if not stored_projection_digest or projection_digest(projection) != stored_projection_digest:
            raise RuntimeError(f"Projection digest mismatch for {path}")
        if str(projection.get("authority_generation_id") or "") != str(
            generation.get("generation_id") or ""
        ):
            raise RuntimeError(f"Projection {path} is outside the current authority generation")
        binding = binding_from_projection(projection)
        scope_mesh = generation.get("scope_meshes", {}).get(scope, {})
        if (
            binding.mesh_id != str(scope_mesh.get("mesh_id") or "")
            or binding.mesh_revision_id != str(scope_mesh.get("mesh_revision_id") or "")
        ):
            raise RuntimeError(f"Projection {path} does not bind the current scoped mesh revision")
        relative = path.relative_to(root).as_posix()
        row = {
            "scope": scope,
            "path": relative,
            "card_id": str(projection.get("id") or ""),
            "projection": projection,
            "binding": binding,
        }
        rows[relative] = row
        manifest_rows.append(
            {
                "scope": scope,
                "path": relative,
                "card_id": row["card_id"],
                "projection_digest": stored_projection_digest,
                **binding.to_dict(),
            }
        )
    manifest_rows.sort(key=lambda item: (item["scope"], item["path"], item["card_id"]))
    manifest_digest = "sha256:" + canonical_digest(manifest_rows)
    if manifest_digest != str(generation.get("projection_manifest_digest") or ""):
        raise RuntimeError("Current model catalog projection manifest digest mismatch")
    if len(manifest_rows) != int(generation.get("projection_count") or 0):
        raise RuntimeError("Current model catalog projection count mismatch")
    scope_order = {scope: index for index, scope in enumerate(CARD_SCOPES)}
    entries = [
        Entry(
            path=root / relative,
            data=dict(row["projection"]),
            source=build_local_entry_source(root, str(row["scope"]), root / relative),
        )
        for relative, row in sorted(
            rows.items(),
            key=lambda item: (
                scope_order.get(str(item[1].get("scope") or ""), len(scope_order)),
                item[0],
            ),
        )
    ]
    return entries, generation


def _entries_from_projection_rows(
    repo_root: Path,
    rows: Iterable[Mapping[str, Any]],
) -> list[Entry]:
    root = Path(repo_root).resolve()
    scope_order = {scope: index for index, scope in enumerate(CARD_SCOPES)}
    normalized = sorted(
        (dict(row) for row in rows),
        key=lambda row: (
            scope_order.get(str(row.get("scope") or ""), len(scope_order)),
            str(row.get("path") or ""),
        ),
    )
    return [
        Entry(
            path=root / str(row["path"]),
            data=dict(row["projection"]),
            source=build_local_entry_source(
                root,
                str(row["scope"]),
                root / str(row["path"]),
            ),
        )
        for row in normalized
    ]


def _preserved_mesh_structure(
    repo_root: Path,
    generation: Mapping[str, Any],
    target_bindings: Mapping[str, LogicGuardBinding],
) -> tuple[dict[str, list[GroundedModelRelation]], dict[str, list[GroundedMembership]], dict[str, list[dict[str, Any]]]]:
    relations = {scope: [] for scope in AUTHORITY_SCOPES}
    memberships = {scope: [] for scope in AUTHORITY_SCOPES}
    unresolved = {scope: [] for scope in AUTHORITY_SCOPES}
    target_keys = {
        scope: {(item.model_id, item.revision_id) for item in target_bindings.values() if item.authority_scope == scope}
        for scope in AUTHORITY_SCOPES
    }
    for scope, mesh_binding in generation.get("scope_meshes", {}).items():
        if scope not in AUTHORITY_SCOPES or not isinstance(mesh_binding, Mapping):
            continue
        probe = next(
            (item for item in target_bindings.values() if item.authority_scope == scope),
            None,
        )
        if probe is None:
            continue
        old_binding = LogicGuardBinding(
            authority_scope=scope,
            model_id=probe.model_id,
            node_id=probe.node_id,
            block_id=probe.block_id,
            revision_id=probe.revision_id,
            mesh_id=str(mesh_binding.get("mesh_id") or ""),
            mesh_revision_id=str(mesh_binding.get("mesh_revision_id") or ""),
        )
        store = open_mesh_store(repo_root, scope)
        mesh = store.get(old_binding.mesh_id, old_binding.mesh_revision_id)
        for item in mesh.metadata.get("unresolved_relationships", []):
            if isinstance(item, Mapping):
                unresolved[scope].append(dict(item))
        for edge in mesh.cross_model_edges:
            source_key = (str(edge.source.model_id), str(edge.source.revision))
            target_key = (str(edge.target.model_id), str(edge.target.revision))
            if source_key in target_keys[scope] and target_key in target_keys[scope]:
                source = next(item for item in target_bindings.values() if (item.model_id, item.revision_id) == source_key)
                target = next(item for item in target_bindings.values() if (item.model_id, item.revision_id) == target_key)
                relations[scope].append(
                    GroundedModelRelation(
                        relation_id=str(edge.id),
                        source=source,
                        target=target,
                        edge_type=str(edge.type),
                        explanation=str(edge.explanation),
                        provenance=tuple(item.to_dict() for item in edge.provenance),
                        weight=float(edge.weight),
                        metadata=dict(edge.metadata),
                    )
                )
            else:
                unresolved[scope].append(
                    {
                        "relation_id": str(edge.id),
                        "disposition": "revalidation-required-after-model-revision",
                        "source": edge.source.to_dict(),
                        "target": edge.target.to_dict(),
                    }
                )
        for membership in mesh.memberships:
            owner_key = (str(membership.owner.model_id), str(membership.owner.revision))
            logical_key = (
                str(membership.logical_model.model_id),
                str(membership.logical_model.revision),
            )
            if owner_key in target_keys[scope] and logical_key in target_keys[scope]:
                owner = next(item for item in target_bindings.values() if (item.model_id, item.revision_id) == owner_key)
                logical = next(item for item in target_bindings.values() if (item.model_id, item.revision_id) == logical_key)
                memberships[scope].append(
                    GroundedMembership(
                        owner=owner,
                        logical_model=logical,
                        roles=tuple(membership.roles),
                        role_metadata=dict(membership.role_metadata),
                        provenance=tuple(item.to_dict() for item in membership.provenance),
                    )
                )
    return relations, memberships, unresolved


def _projection_manifest(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "scope": str(row.get("scope") or ""),
                "path": str(row.get("path") or ""),
                "card_id": str(row.get("card_id") or ""),
                "projection_digest": str(row.get("projection", {}).get("projection_digest") or ""),
                **dict(row.get("binding") or {}),
            }
            for row in rows
        ],
        key=lambda item: (item["scope"], item["path"], item["card_id"]),
    )


def _gap_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    cards_with_gaps = 0
    ledger: list[dict[str, Any]] = []
    required_inputs = {
        "context": "a bounded applicability condition",
        "action": "an explicit action or method",
        "evidence": "independent observed or source-backed evidence",
        "warrant": "an explicit rule connecting the support to the prediction",
        "assumption": "a declared assumption with a reviewable failure condition",
        "opposition": "a rebuttal, counterexample, or undercutting condition",
        "boundary": "a qualifier, limitation, or boundary condition",
    }
    for row in rows:
        projection = row.get("projection") if isinstance(row.get("projection"), Mapping) else {}
        gaps = [str(item) for item in projection.get("logicguard_open_role_gaps", []) if str(item)]
        if gaps:
            cards_with_gaps += 1
        for gap in gaps:
            counts[gap] = counts.get(gap, 0) + 1
            binding = (
                dict(row.get("binding") or {})
                if isinstance(row.get("binding"), Mapping)
                else {}
            )
            gap_identity = {
                "card_id": str(
                    row.get("card_id") or projection.get("id") or ""
                ),
                "authority_scope": str(
                    binding.get("authority_scope")
                    or projection.get("authority_scope")
                    or ""
                ),
                "model_id": str(
                    binding.get("model_id")
                    or projection.get("logicguard_model_id")
                    or ""
                ),
                "revision_id": str(
                    binding.get("revision_id")
                    or projection.get("logicguard_revision_id")
                    or ""
                ),
                "mesh_revision_id": str(
                    binding.get("mesh_revision_id")
                    or projection.get("logicguard_mesh_revision_id")
                    or ""
                ),
                "gap_kind": gap,
            }
            ledger.append(
                {
                    "gap_id": "model-gap-" + canonical_digest(gap_identity)[:24],
                    **gap_identity,
                    "disposition": "open-awaiting-grounded-input",
                    "required_input": required_inputs.get(
                        gap,
                        "grounded evidence that closes the declared structural gap",
                    ),
                    "reopen_condition": {
                        "kind": "new-grounded-model-input",
                        "gap_kind": gap,
                        "exact_revision_required": True,
                    },
                    "owner": SLEEP_AUTHORITY_WRITER,
                    "claim_boundary": (
                        "The gap is explicitly tracked; Sleep has not invented the missing support."
                    ),
                }
            )
    ledger.sort(
        key=lambda item: (
            item["authority_scope"],
            item["card_id"],
            item["model_id"],
            item["gap_kind"],
        )
    )
    return {
        "cards_with_gaps": cards_with_gaps,
        "gap_counts": dict(sorted(counts.items())),
        "gap_ledger": ledger,
        "reviewed_gap_count": len(ledger),
        "all_gaps_dispositioned": all(
            item.get("disposition") == "open-awaiting-grounded-input"
            and bool(item.get("required_input"))
            and bool(item.get("reopen_condition"))
            for item in ledger
        ),
    }


def publish_sleep_model_generation(
    repo_root: Path,
    *,
    reason: str,
    card_upserts: Mapping[str | Path, Mapping[str, Any]] | None = None,
    card_deletes: Sequence[str | Path] = (),
    relations: Sequence[GroundedModelRelation] = (),
    unresolved_relationships: Sequence[Mapping[str, Any]] = (),
    actor: str = SLEEP_AUTHORITY_WRITER,
    refresh_index_on_no_delta: bool = True,
    validate_index_on_no_delta: bool = True,
    refresh_index_on_commit: bool = True,
    validate_index_on_commit: bool = True,
    include_runtime_catalog: bool = False,
) -> dict[str, Any]:
    """Publish one Sleep-owned model/mesh/projection/index generation atomically."""

    if actor != SLEEP_AUTHORITY_WRITER:
        raise PermissionError("Only the Sleep authority owner may publish a normal-runtime model generation")
    root = Path(repo_root).resolve()
    authority_recovery = recover_authority_scopes(root)
    if not authority_recovery.get("ok"):
        raise RuntimeError(
            "Sleep model authority recovery failed: "
            + "; ".join(authority_recovery.get("issues", []))
        )
    normalized_upserts: dict[str, tuple[str, Path, dict[str, Any]]] = {}
    for path_value, payload in (card_upserts or {}).items():
        scope, relative, path = _relative_card_path(root, path_value)
        normalized_upserts[relative] = (scope, path, _json_safe(dict(payload)))
    normalized_deletes = {_relative_card_path(root, item)[1] for item in card_deletes}
    if normalized_deletes.intersection(normalized_upserts):
        raise ValueError("A card path cannot be upserted and deleted in the same Sleep generation")
    generation_before, current_rows = _current_projection_rows(
        root,
        replacing_paths=tuple(normalized_upserts),
    )

    operation_source = {
        "current_generation_digest": str(generation_before.get("pointer_digest") or ""),
        "reason": str(reason),
        "upserts": {path: canonical_digest(payload[2]) for path, payload in sorted(normalized_upserts.items())},
        "deletes": sorted(normalized_deletes),
        "relations": [item.relation_id for item in relations],
        "unresolved_relationships": _json_safe(list(unresolved_relationships)),
    }
    operation_id = "sleep-generation-" + canonical_digest(operation_source)[:32]
    if not normalized_upserts and not normalized_deletes and not relations and not unresolved_relationships:
        pointer_exists = authority_generation_pointer_path(root).exists()
        index_receipt = {}
        if not pointer_exists:
            publish_authority_generation(root, generation_before, writer=actor)
        if refresh_index_on_no_delta:
            index_receipt = rebuild_active_index(
                root,
                reason=reason,
                authority_generation=None if pointer_exists else generation_before,
                publisher_id=actor,
            )
        validation = (
            validate_active_index(root)
            if validate_index_on_no_delta
            else {
                "ok": True,
                "deferred": True,
                "reason": "final Sleep index owner has not run yet",
            }
        )
        if not validation.get("ok"):
            raise RuntimeError("Sleep no-delta index refresh failed: " + "; ".join(validation.get("issues", [])))
        result = {
            "ok": True,
            "status": "no_delta",
            "idempotent_no_delta": True,
            "generation_id": str(generation_before.get("generation_id") or ""),
            "authority_generation_digest": str(
                generation_before.get("pointer_digest") or ""
            ),
            "scope_meshes": dict(generation_before.get("scope_meshes") or {}),
            "projection_count": int(
                generation_before.get("projection_count") or 0
            ),
            "projection_manifest_digest": str(
                generation_before.get("projection_manifest_digest") or ""
            ),
            "index_receipt": index_receipt,
            "index_validation": validation,
            "model_diagnostics": _gap_summary(current_rows.values()),
            "authority_recovery": authority_recovery,
        }
        if include_runtime_catalog:
            result["_runtime_catalog_entries"] = _entries_from_projection_rows(
                root,
                current_rows.values(),
            )
        return result

    snapshot = _snapshot_active_authority(root, operation_id)
    try:
        target_rows = {
            path: dict(row)
            for path, row in current_rows.items()
            if path not in normalized_deletes and path not in normalized_upserts
        }
        target_bindings: dict[str, LogicGuardBinding] = {
            path: row["binding"] for path, row in target_rows.items()
        }
        for relative, (scope, _path, payload) in sorted(normalized_upserts.items()):
            model_id = str(payload.get("id") or "")
            if not model_id:
                raise ValueError(f"Sleep upsert {relative} has no card id")
            store = open_model_store(root, scope)
            from local_kb.logicguard_models import model_id_for_card

            head = store.head(model_id_for_card(model_id))
            result = commit_card_model(
                root,
                payload,
                authority_scope=scope,
                expected_revision=str(head) if head is not None else None,
                idempotency_key=f"{operation_id}:model:{scope}:{model_id}",
                actor=actor,
                source_reference=relative,
            )
            target_rows[relative] = {
                "scope": scope,
                "path": relative,
                "card_id": model_id,
                "binding": result.binding,
            }
            target_bindings[relative] = result.binding

        ids: dict[tuple[str, str], str] = {}
        for path, row in target_rows.items():
            identity = (str(row["scope"]), str(row["card_id"]))
            if identity in ids:
                raise ValueError(f"Duplicate card id {identity[1]} in authority scope {identity[0]}")
            ids[identity] = path

        preserved_relations, preserved_memberships, unresolved_by_scope = _preserved_mesh_structure(
            root,
            generation_before,
            target_bindings,
        )
        for relation in relations:
            preserved_relations[relation.source.authority_scope].append(relation)
        for item in unresolved_relationships:
            scope = str(item.get("authority_scope") or "")
            if scope not in AUTHORITY_SCOPES:
                raise ValueError("Unresolved relationship requires an exact authority_scope")
            unresolved_by_scope[scope].append(dict(item))

        for scope in AUTHORITY_SCOPES:
            unique_relations: dict[str, GroundedModelRelation] = {}
            for relation in preserved_relations[scope]:
                previous = unique_relations.get(relation.relation_id)
                if previous is not None and previous != relation:
                    raise ValueError(
                        f"Conflicting grounded relation id {relation.relation_id} in {scope} authority"
                    )
                unique_relations[relation.relation_id] = relation
            preserved_relations[scope] = list(unique_relations.values())

            unique_memberships: list[GroundedMembership] = []
            for membership in preserved_memberships[scope]:
                if membership not in unique_memberships:
                    unique_memberships.append(membership)
            preserved_memberships[scope] = unique_memberships

            unique_unresolved: dict[str, dict[str, Any]] = {}
            for unresolved in unresolved_by_scope[scope]:
                normalized = _json_safe(dict(unresolved))
                unique_unresolved[canonical_digest(normalized)] = normalized
            unresolved_by_scope[scope] = list(unique_unresolved.values())

        scope_meshes: dict[str, dict[str, Any]] = {}
        rebound: dict[tuple[str, str, str], LogicGuardBinding] = {}
        for scope in AUTHORITY_SCOPES:
            bindings = tuple(item for item in target_bindings.values() if item.authority_scope == scope)
            if not bindings:
                continue
            mesh_store = open_mesh_store(root, scope)
            head = mesh_store.head(mesh_id_for_scope(scope))
            mesh = commit_scope_mesh(
                root,
                authority_scope=scope,
                model_bindings=bindings,
                expected_revision=str(head) if head is not None else None,
                idempotency_key=f"{operation_id}:mesh:{scope}",
                actor=actor,
                relations=tuple(preserved_relations[scope]),
                memberships=tuple(preserved_memberships[scope]),
                unresolved_relationships=tuple(unresolved_by_scope[scope]),
            )
            scope_meshes[scope] = {
                "mesh_id": mesh.mesh_id,
                "mesh_revision_id": mesh.mesh_revision_id,
                "content_digest": mesh.content_digest,
            }
            for item in mesh.bindings:
                rebound[(scope, item.model_id, item.revision_id)] = item

        generation_identity = {
            "operation": operation_source,
            "bindings": [
                {
                    "path": path,
                    **target_bindings[path].to_dict(),
                    "mesh": scope_meshes.get(target_bindings[path].authority_scope, {}),
                }
                for path in sorted(target_bindings)
            ],
        }
        generation_id = "generation-" + canonical_digest(generation_identity)[:32]
        projected_rows: list[dict[str, Any]] = []
        for scope in AUTHORITY_SCOPES:
            scoped_rows: list[tuple[str, dict[str, Any], LogicGuardBinding]] = []
            for relative, row in sorted(target_rows.items()):
                binding = target_bindings[relative]
                if binding.authority_scope != scope:
                    continue
                exact = rebound[(scope, binding.model_id, binding.revision_id)]
                scoped_rows.append((relative, row, exact))
            projections = project_cards(
                root,
                [exact for _relative, _row, exact in scoped_rows],
                authority_generation_id=generation_id,
            )
            for (relative, row, exact), projection in zip(
                scoped_rows,
                projections,
                strict=True,
            ):
                projected_rows.append(
                    {
                        "scope": row["scope"],
                        "path": relative,
                        "card_id": row["card_id"],
                        "binding": exact.to_dict(),
                        "projection": projection,
                    }
                )
        projected_rows.sort(key=lambda row: (str(row["scope"]), str(row["path"])))
        manifest = _projection_manifest(projected_rows)
        generation = build_authority_generation_payload(
            generation_id=generation_id,
            scope_meshes=scope_meshes,
            projection_manifest_digest="sha256:" + canonical_digest(manifest),
            projection_count=len(projected_rows),
            actor=actor,
        )

        for path in normalized_deletes:
            target = root / path
            if target.exists():
                target.unlink()
        write_card_projections_atomic(
            root,
            [(root / row["path"], row["projection"]) for row in projected_rows],
        )
        published = publish_authority_generation(root, generation, writer=actor)
        index_receipt = {}
        if refresh_index_on_commit:
            index_receipt = rebuild_active_index(
                root,
                reason=reason,
                authority_generation=generation,
                publisher_id=actor,
            )
        index_validation = (
            validate_active_index(root)
            if validate_index_on_commit
            else {
                "ok": True,
                "deferred": True,
                "reason": "final Sleep index owner has not run yet",
            }
        )
        if not index_validation.get("ok"):
            raise RuntimeError("Sleep generation index validation failed: " + "; ".join(index_validation.get("issues", [])))
        validate_card_projections(
            root,
            [row["projection"] for row in projected_rows],
        )

        receipt = {
            "schema_version": MODEL_GENERATION_RECEIPT_SCHEMA,
            "status": "committed",
            "operation_id": operation_id,
            "generation_id": generation_id,
            "reason": reason,
            "actor": actor,
            "committed_at": utc_now_iso(),
            "upsert_count": len(normalized_upserts),
            "delete_count": len(normalized_deletes),
            "projection_count": len(projected_rows),
            "scope_meshes": scope_meshes,
            "projection_manifest_digest": generation["projection_manifest_digest"],
            "authority_generation_digest": published["pointer_digest"],
            "index_receipt": index_receipt,
            "index_validation": index_validation,
            "model_diagnostics": _gap_summary(projected_rows),
            "authority_recovery": authority_recovery,
            "unresolved_relationship_count": sum(len(items) for items in unresolved_by_scope.values()),
            "claim_boundary": "Sleep published current model structure; it did not establish factual truth.",
        }
        receipt["receipt_digest"] = "sha256:" + canonical_digest(receipt)
        receipt_path = root / "kb" / "history" / "model-generations" / f"{generation_id}.json"
        _atomic_json(receipt_path, receipt)
        _cleanup_snapshot(root, snapshot)
        result = {
            "ok": True,
            "status": "committed",
            "idempotent_no_delta": False,
            "receipt": receipt,
        }
        if include_runtime_catalog:
            result["_runtime_catalog_entries"] = _entries_from_projection_rows(
                root,
                projected_rows,
            )
        return result
    except Exception as exc:
        rollback = _restore_active_authority(root, snapshot)
        failure = {
            "schema_version": MODEL_GENERATION_RECEIPT_SCHEMA,
            "status": "rolled_back",
            "operation_id": operation_id,
            "reason": reason,
            "failed_at": utc_now_iso(),
            "error": f"{type(exc).__name__}: {exc}",
            "rollback": rollback,
        }
        failure["receipt_digest"] = "sha256:" + canonical_digest(failure)
        _atomic_json(
            root / "kb" / "history" / "model-generations" / f"{operation_id}-failed.json",
            failure,
        )
        return {"ok": False, **failure}
