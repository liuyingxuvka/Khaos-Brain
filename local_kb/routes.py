from __future__ import annotations

import os

from local_kb.common import normalize_text, normalize_string_list, parse_route_segments
from local_kb.models import Entry, RouteBranch
from local_kb.store import load_entries


def _matches_prefix(route: list[str], prefix: list[str]) -> bool:
    return route[: len(prefix)] == prefix


def _entry_id(entry: Entry) -> str:
    return str(entry.data.get("id") or entry.path.stem)


def _direct_card_summary(entry: Entry, repo_root: os.PathLike[str]) -> dict[str, object]:
    return {
        "id": entry.data.get("id"),
        "title": entry.data.get("title"),
        "status": entry.data.get("status"),
        "domain_path": parse_route_segments(entry.data.get("domain_path", [])),
        "path": os.path.relpath(entry.path, repo_root),
    }


def build_route_view(
    entries: list[Entry],
    repo_root: os.PathLike[str],
    route: str = "",
    include_cross_index: bool = False,
) -> dict[str, object]:
    prefix = parse_route_segments(route)
    branches: dict[str, RouteBranch] = {}
    direct_cards: dict[str, Entry] = {}

    for entry in entries:
        entry_id = _entry_id(entry)
        primary_route = parse_route_segments(entry.data.get("domain_path", []))
        if _matches_prefix(primary_route, prefix):
            if len(primary_route) == len(prefix):
                direct_cards[entry_id] = entry
            elif len(primary_route) > len(prefix):
                segment = primary_route[len(prefix)]
                branch = branches.setdefault(
                    segment,
                    RouteBranch(segment=segment, route=prefix + [segment]),
                )
                branch.entry_ids.add(entry_id)
                if len(primary_route) == len(prefix) + 1:
                    branch.direct_entry_ids.add(entry_id)

        if not include_cross_index:
            continue

        for cross_route in normalize_string_list(entry.data.get("cross_index", [])):
            cross_segments = parse_route_segments(cross_route)
            if not _matches_prefix(cross_segments, prefix) or len(cross_segments) <= len(prefix):
                continue
            segment = cross_segments[len(prefix)]
            branch = branches.setdefault(
                segment,
                RouteBranch(segment=segment, route=prefix + [segment]),
            )
            branch.entry_ids.add(entry_id)
            if len(cross_segments) == len(prefix) + 1:
                branch.direct_entry_ids.add(entry_id)

    children = []
    for index, branch in enumerate(sorted(branches.values(), key=lambda item: item.segment), start=1):
        children.append(
            {
                "index": index,
                "segment": branch.segment,
                "route": branch.route,
                "entry_count": len(branch.entry_ids),
                "direct_entry_count": len(branch.direct_entry_ids),
            }
        )

    direct_card_payload = [
        _direct_card_summary(entry, repo_root)
        for entry in sorted(direct_cards.values(), key=lambda item: normalize_text(item.data.get("title", "")))
    ]

    return {
        "route": prefix,
        "route_label": " / ".join(prefix) if prefix else "root",
        "children": children,
        "direct_cards": direct_card_payload,
    }


def select_child_routes(view: dict[str, object], raw_selection: str) -> list[list[str]]:
    if not raw_selection.strip():
        return []
    children = {item["index"]: item["route"] for item in view["children"] if isinstance(item, dict)}
    selected_routes: list[list[str]] = []
    for chunk in raw_selection.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        index = int(chunk)
        if index not in children:
            raise ValueError(f"Unknown route index: {index}")
        selected_routes.append(list(children[index]))
    return selected_routes


def build_selected_views(
    repo_root: os.PathLike[str],
    route: str,
    selection: str,
    include_cross_index: bool = False,
) -> list[dict[str, object]]:
    entries = load_entries(repo_root)
    current_view = build_route_view(entries, repo_root, route=route, include_cross_index=include_cross_index)
    selected_routes = select_child_routes(current_view, selection)
    return [
        build_route_view(entries, repo_root, route="/".join(selected_route), include_cross_index=include_cross_index)
        for selected_route in selected_routes
    ]


def format_route_view(view: dict[str, object]) -> str:
    lines = [f"Route: {view['route_label']}", ""]

    children = view["children"]
    lines.append("Children:")
    if children:
        for child in children:
            lines.append(
                f"{child['index']}. {child['segment']} "
                f"(subtree_cards={child['entry_count']} direct_cards={child['direct_entry_count']})"
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

