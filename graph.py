"""
graph.py
Builds a file-level dependency graph from scanner records by matching
each import string against the module/file names actually present in
the repo. Provides forward/reverse adjacency, BFS-based impact
analysis, and a Mermaid flowchart exporter.
"""

import os
from collections import deque


def _module_key(path):
    """Turn a relative file path into candidate module-name keys."""
    stem = os.path.splitext(path)[0]
    parts = stem.replace(os.sep, "/").split("/")
    keys = {parts[-1]}  # bare filename, e.g. "OrderService"
    keys.add("/".join(parts))  # full relative stem
    keys.add(".".join(parts))  # dotted, python-style
    return keys


def build_dependency_graph(records):
    """
    Returns (forward, reverse):
      forward[file] = set of files it depends on
      reverse[file] = set of files that depend on it
    Unresolved imports (external libraries) are simply not linked.
    """
    # index: candidate key -> file path
    index = {}
    for r in records:
        for key in _module_key(r["path"]):
            index.setdefault(key, set()).add(r["path"])

    forward = {r["path"]: set() for r in records}
    reverse = {r["path"]: set() for r in records}

    for r in records:
        for imp in r["imports"]:
            imp_last = imp.replace(".", "/").split("/")[-1]
            candidates = index.get(imp) or index.get(imp_last) or set()
            for target in candidates:
                if target != r["path"]:
                    forward[r["path"]].add(target)
                    reverse[target].add(r["path"])

    return forward, reverse


def impact_analysis(target_file, reverse, forward=None, max_depth=5):
    """
    BFS over `reverse` graph starting at target_file to find every file
    that would be directly or transitively affected by a change to it.
    Returns a dict: {depth: [files]}
    """
    if target_file not in reverse:
        return None

    visited = {target_file}
    frontier = deque([(target_file, 0)])
    by_depth = {}

    while frontier:
        node, depth = frontier.popleft()
        if depth >= max_depth:
            continue
        for dependent in reverse.get(node, ()):
            if dependent not in visited:
                visited.add(dependent)
                by_depth.setdefault(depth + 1, []).append(dependent)
                frontier.append((dependent, depth + 1))

    direct_deps = sorted(forward.get(target_file, [])) if forward else []
    return {
        "target": target_file,
        "directly_imports": direct_deps,
        "affected_by_depth": {d: sorted(files) for d, files in sorted(by_depth.items())},
        "total_affected": len(visited) - 1,
    }


def to_mermaid(forward, records=None, max_nodes=60):
    """Render the dependency graph as a Mermaid flowchart (markdown)."""
    lines = ["```mermaid", "flowchart LR"]

    def node_id(path):
        return "N" + str(abs(hash(path)) % (10 ** 8))

    seen_edges = 0
    files = list(forward.keys())[:max_nodes]
    id_map = {f: node_id(f) for f in files}

    lang_by_path = {}
    if records:
        lang_by_path = {r["path"]: r["language"] for r in records}

    for f in files:
        label = f.split("/")[-1]
        lines.append(f'    {id_map[f]}["{label}"]')

    for src in files:
        for dst in forward.get(src, ()):
            if dst in id_map:
                lines.append(f"    {id_map[src]} --> {id_map[dst]}")
                seen_edges += 1

    lines.append("```")
    return "\n".join(lines)
