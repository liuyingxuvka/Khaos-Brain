from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from local_kb.common import normalize_string_list, normalize_text, parse_route_segments
from local_kb.models import Entry
from local_kb.store import load_entries, load_yaml_file


def taxonomy_path(repo_root: Path) -> Path:
    return repo_root / "kb" / "taxonomy.yaml"


def load_taxonomy(repo_root: Path) -> dict[str, Any]:
    path = taxonomy_path(repo_root)
    if not path.exists():
        return {"version": 1, "kind": "official-taxonomy", "nodes": []}
    payload = load_yaml_file(path)
    if not isinstance(payload, dict):
        return {"version": 1, "kind": "official-taxonomy", "nodes": []}
    payload.setdefault("version", 1)
    payload.setdefault("kind", "official-taxonomy")
    payload.setdefault("nodes", [])
    return payload


def _root_node(taxonomy: dict[str, Any]) -> dict[str, Any]:
    return {"segment": "", "children": list(taxonomy.get("nodes", []))}


def _child_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    children = node.get("children", [])
    if not isinstance(children, list):
        return []
    return [child for child in children if isinstance(child, dict) and str(child.get("segment", "")).strip()]


def _find_taxonomy_node(taxonomy: dict[str, Any], route: list[str]) -> dict[str, Any] | None:
    current = _root_node(taxonomy)
    for segment in route:
        next_node = None
        for child in _child_nodes(current):
            if str(child.get("segment", "")).strip().lower() == segment:
                next_node = child
                break
        if next_node is None:
            return None
        current = next_node
    return current


def _declared_routes(taxonomy: dict[str, Any]) -> set[tuple[str, ...]]:
    declared: set[tuple[str, ...]] = {tuple()}

    def walk(children: list[dict[str, Any]], prefix: list[str]) -> None:
        for child in children:
            segment = str(child.get("segment", "")).strip().lower()
            if not segment:
                continue
            route = tuple(prefix + [segment])
            declared.add(route)
            walk(_child_nodes(child), list(route))

    walk(_child_nodes(_root_node(taxonomy)), [])
    return declared


def _entry_id(entry: Entry) -> str:
    return str(entry.data.get("id") or entry.path.stem)


def _route_prefixes(route: list[str]) -> list[tuple[str, ...]]:
    return [tuple(route[:index]) for index in range(len(route) + 1)]


def _empty_count_bucket() -> dict[str, set[str]]:
    return {
        "primary_subtree_ids": set(),
        "primary_direct_ids": set(),
        "observed_subtree_ids": set(),
        "observed_direct_ids": set(),
    }


def derive_route_counts(entries: list[Entry]) -> dict[tuple[str, ...], dict[str, set[str]]]:
    counts: dict[tuple[str, ...], dict[str, set[str]]] = {}

    def ensure_bucket(route: tuple[str, ...]) -> dict[str, set[str]]:
        bucket = counts.get(route)
        if bucket is None:
            bucket = _empty_count_bucket()
            counts[route] = bucket
        return bucket

    def add_route(entry_id: str, route: list[str], primary: bool) -> None:
        if not route:
            return
        for prefix in _route_prefixes(route):
            bucket = ensure_bucket(prefix)
            bucket["observed_subtree_ids"].add(entry_id)
            if primary:
                bucket["primary_subtree_ids"].add(entry_id)
        direct_bucket = ensure_bucket(tuple(route))
        direct_bucket["observed_direct_ids"].add(entry_id)
        if primary:
            direct_bucket["primary_direct_ids"].add(entry_id)

    ensure_bucket(tuple())
    for entry in entries:
        entry_id = _entry_id(entry)
        primary_route = parse_route_segments(entry.data.get("domain_path", []))
        add_route(entry_id, primary_route, primary=True)
        for cross_route in normalize_string_list(entry.data.get("cross_index", [])):
            cross_segments = parse_route_segments(cross_route)
            add_route(entry_id, cross_segments, primary=False)
    return counts


def _exact_primary_cards(entries: list[Entry], repo_root: Path, route: list[str]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for entry in entries:
        primary_route = parse_route_segments(entry.data.get("domain_path", []))
        if primary_route != route:
            continue
        payload.append(
            {
                "id": entry.data.get("id"),
                "title": entry.data.get("title"),
                "status": entry.data.get("status"),
                "path": os.path.relpath(entry.path, repo_root),
            }
        )
    return sorted(payload, key=lambda item: normalize_text(item.get("title", "")))


def _child_payload(
    route: list[str],
    segment: str,
    counts: dict[tuple[str, ...], dict[str, set[str]]],
    *,
    declared: bool,
) -> dict[str, object]:
    child_route = route + [segment]
    bucket = counts.get(tuple(child_route), _empty_count_bucket())
    return {
        "segment": segment,
        "route": child_route,
        "declared": declared,
        "primary_subtree_count": len(bucket["primary_subtree_ids"]),
        "primary_direct_count": len(bucket["primary_direct_ids"]),
        "observed_subtree_count": len(bucket["observed_subtree_ids"]),
        "observed_direct_count": len(bucket["observed_direct_ids"]),
    }


def build_taxonomy_view(repo_root: Path, route: str = "") -> dict[str, object]:
    taxonomy = load_taxonomy(repo_root)
    entries = load_entries(repo_root)
    counts = derive_route_counts(entries)
    prefix = parse_route_segments(route)
    node = _find_taxonomy_node(taxonomy, prefix)
    declared = not prefix or node is not None
    active_node = node if node is not None else {"children": []}

    declared_children = [
        _child_payload(prefix, str(child.get("segment", "")).strip().lower(), counts, declared=True)
        for child in _child_nodes(active_node)
    ]
    declared_children = sorted(declared_children, key=lambda item: str(item["segment"]))
    for index, child in enumerate(declared_children, start=1):
        child["index"] = index

    declared_segments = {str(child["segment"]) for child in declared_children}
    prefix_tuple = tuple(prefix)
    undeclared_children: list[dict[str, object]] = []
    for observed_route in counts:
        if len(observed_route) != len(prefix) + 1:
            continue
        if list(observed_route[: len(prefix)]) != prefix:
            continue
        segment = observed_route[-1]
        if segment in declared_segments:
            continue
        undeclared_children.append(_child_payload(prefix, segment, counts, declared=False))
    undeclared_children = sorted(undeclared_children, key=lambda item: str(item["segment"]))

    direct_cards = _exact_primary_cards(entries, repo_root, prefix)
    bucket = counts.get(prefix_tuple, _empty_count_bucket())

    return {
        "route": prefix,
        "route_label": " / ".join(prefix) if prefix else "root",
        "declared": declared,
        "declared_child_count": len(declared_children),
        "children": declared_children,
        "direct_cards": direct_cards,
        "coverage": {
            "primary_subtree_count": len(bucket["primary_subtree_ids"]),
            "primary_direct_count": len(bucket["primary_direct_ids"]),
            "observed_subtree_count": len(bucket["observed_subtree_ids"]),
            "observed_direct_count": len(bucket["observed_direct_ids"]),
            "undeclared_child_count": len(undeclared_children),
            "undeclared_children": undeclared_children,
        },
    }


def build_taxonomy_gap_report(repo_root: Path) -> dict[str, object]:
    taxonomy = load_taxonomy(repo_root)
    entries = load_entries(repo_root)
    counts = derive_route_counts(entries)
    declared_routes = _declared_routes(taxonomy)

    gap_payload: dict[tuple[str, ...], dict[str, Any]] = {}
    observed_routes = [route for route in counts if route]
    for observed_route in sorted(observed_routes, key=lambda item: (len(item), item)):
        if observed_route in declared_routes:
            continue

        first_missing: tuple[str, ...] | None = None
        for index in range(1, len(observed_route) + 1):
            prefix = observed_route[:index]
            if prefix not in declared_routes:
                first_missing = prefix
                break
        if first_missing is None:
            continue

        bucket = counts.get(first_missing, _empty_count_bucket())
        gap = gap_payload.setdefault(
            first_missing,
            {
                "route": list(first_missing),
                "route_label": " / ".join(first_missing),
                "parent_route": list(first_missing[:-1]),
                "segment": first_missing[-1],
                "observed_subtree_count": len(bucket["observed_subtree_ids"]),
                "observed_direct_count": len(bucket["observed_direct_ids"]),
                "primary_subtree_count": len(bucket["primary_subtree_ids"]),
                "recommended_action": "review-taxonomy-add",
                "example_observed_routes": [],
            },
        )
        example_routes = gap["example_observed_routes"]
        route_label = " / ".join(observed_route)
        if route_label not in example_routes and len(example_routes) < 3:
            example_routes.append(route_label)

    gaps = sorted(
        gap_payload.values(),
        key=lambda item: (
            -int(item["observed_subtree_count"]),
            len(item["route"]),
            str(item["route_label"]),
        ),
    )
    return {
        "kind": "local-kb-taxonomy-gap-report",
        "route_count": len(gaps),
        "gaps": gaps,
    }


def format_taxonomy_view(view: dict[str, object]) -> str:
    lines = [f"Taxonomy route: {view['route_label']}", f"Declared: {view['declared']}", ""]

    coverage = view["coverage"]
    lines.append(
        "Coverage: "
        f"primary_subtree={coverage['primary_subtree_count']} "
        f"primary_direct={coverage['primary_direct_count']} "
        f"observed_subtree={coverage['observed_subtree_count']} "
        f"observed_direct={coverage['observed_direct_count']}"
    )
    lines.append("")

    lines.append("Declared children:")
    children = view["children"]
    if children:
        for child in children:
            lines.append(
                f"{child['index']}. {child['segment']} "
                f"(primary_subtree={child['primary_subtree_count']} "
                f"observed_subtree={child['observed_subtree_count']})"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Undeclared observed children:")
    undeclared = coverage["undeclared_children"]
    if undeclared:
        for child in undeclared:
            lines.append(
                f"- {child['segment']} "
                f"(observed_subtree={child['observed_subtree_count']} "
                f"observed_direct={child['observed_direct_count']})"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Direct cards:")
    direct_cards = view["direct_cards"]
    if direct_cards:
        for card in direct_cards:
            lines.append(f"- [{card['id']}] {card['title']} ({card['status']})")
    else:
        lines.append("- none")
    return "\n".join(lines)


def format_taxonomy_gap_report(report: dict[str, object]) -> str:
    lines = ["Taxonomy gaps:", ""]
    gaps = report["gaps"]
    if not gaps:
        lines.append("- none")
        return "\n".join(lines)

    for gap in gaps:
        lines.append(
            f"- {gap['route_label']} "
            f"(observed_subtree={gap['observed_subtree_count']} "
            f"observed_direct={gap['observed_direct_count']} "
            f"primary_subtree={gap['primary_subtree_count']})"
        )
        example_routes = gap["example_observed_routes"]
        if example_routes:
            lines.append(f"  examples={'; '.join(example_routes)}")
    return "\n".join(lines)
