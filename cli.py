"""
cli.py -- LegacyBrain AI (prototype)
Terminal entry point tying together scanning, knowledge base,
dependency graph, impact analysis, and doc/diagram generation.

Usage:
    python -m legacybrain.cli scan   <repo_path>
    python -m legacybrain.cli ask    "<question>"   [--repo <repo_path>]
    python -m legacybrain.cli impact <file_path>     [--repo <repo_path>]
    python -m legacybrain.cli docs   [--repo <repo_path>] [--out docs]
    python -m legacybrain.cli graph  [--repo <repo_path>] [--out architecture.md]
    python -m legacybrain.cli stats  [--repo <repo_path>]
"""

import argparse
import json
import os
import sys

from . import scanner, graph as graph_mod, knowledge_base as kbmod, docgen


def _resolve_repo(args_repo):
    return os.path.abspath(args_repo or ".")


def cmd_scan(args):
    repo = _resolve_repo(args.repo_path)
    print(f"Scanning {repo} ...")
    records = scanner.scan_repo(repo)
    if not records:
        print("No supported source files found (.py .java .js .jsx .ts .tsx .go).")
        return
    kb = kbmod.build_knowledge_base(records)
    saved_to = kbmod.save_kb(kb, repo)
    print(f"Indexed {len(records)} files -> {saved_to}")

    forward, _ = graph_mod.build_dependency_graph(records)
    total_edges = sum(len(v) for v in forward.values())
    print(f"Resolved {total_edges} internal dependency edges.")
    print("\nNext steps:")
    print(f'  python -m legacybrain.cli ask "where is payment calculated" --repo {repo}')
    print(f"  python -m legacybrain.cli graph --repo {repo}")
    print(f"  python -m legacybrain.cli docs --repo {repo}")


def _load_or_die(repo):
    kb = kbmod.load_kb(repo)
    if kb is None:
        print(f"No knowledge base found for {repo}. Run `scan` first.")
        sys.exit(1)
    return kb


def cmd_ask(args):
    repo = _resolve_repo(args.repo)
    kb = _load_or_die(repo)
    results = kbmod.search(kb, args.question, top_k=args.top_k)

    if not results:
        print("No matching files found. Try different keywords.")
        return

    print(f'\nQuery: "{args.question}"\n')
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['file']}  (confidence: {r['confidence']})")
        if r["matched_classes"]:
            print(f"   classes:   {', '.join(r['matched_classes'])}")
        if r["matched_functions"]:
            print(f"   functions: {', '.join(r['matched_functions'])}")
        if r["imports"]:
            print(f"   imports:   {', '.join(r['imports'])}")
        print()


def cmd_impact(args):
    repo = _resolve_repo(args.repo)
    kb = _load_or_die(repo)
    records = [entry["record"] for entry in kb["files"].values()]
    forward, reverse = graph_mod.build_dependency_graph(records)

    target = args.file_path.replace(os.sep, "/")
    if target not in reverse:
        matches = [p for p in reverse if p.endswith(target)]
        if len(matches) == 1:
            target = matches[0]
        elif len(matches) > 1:
            print(f"Ambiguous path '{args.file_path}'. Candidates:")
            for m in matches:
                print(f"  - {m}")
            return
        else:
            print(f"File not found in knowledge base: {args.file_path}")
            return

    result = graph_mod.impact_analysis(target, reverse, forward)
    print(f"\nImpact analysis for: {result['target']}\n")
    print(f"Directly imports ({len(result['directly_imports'])}):")
    for f in result["directly_imports"]:
        print(f"  - {f}")

    print(f"\nFiles affected if this changes (total: {result['total_affected']}):")
    for depth, files in result["affected_by_depth"].items():
        print(f"  depth {depth}:")
        for f in files:
            print(f"    - {f}")

    if result["total_affected"] == 0:
        print("  (none -- safe to change in isolation, but check test coverage)")
    print("\nTesting recommendation: prioritize tests covering the files listed above,")
    print("starting with depth 1 (direct dependents).")


def cmd_docs(args):
    repo = _resolve_repo(args.repo)
    kb = _load_or_die(repo)
    records = [entry["record"] for entry in kb["files"].values()]
    forward, _ = graph_mod.build_dependency_graph(records)

    out_dir = os.path.join(repo, args.out)
    written = docgen.generate_docs(records, out_dir)
    summary = docgen.generate_architecture_summary(records, forward)
    summary_path = os.path.join(out_dir, "ARCHITECTURE_SUMMARY.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(f"Wrote {len(written)} file docs + architecture summary to {out_dir}/")


def cmd_graph(args):
    repo = _resolve_repo(args.repo)
    kb = _load_or_die(repo)
    records = [entry["record"] for entry in kb["files"].values()]
    forward, _ = graph_mod.build_dependency_graph(records)
    mermaid = graph_mod.to_mermaid(forward, records)

    out_path = os.path.join(repo, args.out)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Module Dependency Graph\n\n" + mermaid + "\n")
    print(f"Wrote dependency graph -> {out_path}")
    print("(Open in any Markdown viewer that supports Mermaid, e.g. GitHub or VS Code.)")


def cmd_stats(args):
    repo = _resolve_repo(args.repo)
    kb = _load_or_die(repo)
    records = [entry["record"] for entry in kb["files"].values()]
    forward, _ = graph_mod.build_dependency_graph(records)
    print(docgen.generate_architecture_summary(records, forward))


def build_parser():
    p = argparse.ArgumentParser(prog="legacybrain", description="LegacyBrain AI -- legacy codebase copilot (prototype)")
    sub = p.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="scan a repository and build the knowledge base")
    p_scan.add_argument("repo_path", help="path to the repository to scan")
    p_scan.set_defaults(func=cmd_scan)

    p_ask = sub.add_parser("ask", help="ask a natural-language question about the codebase")
    p_ask.add_argument("question")
    p_ask.add_argument("--repo", default=".", help="repository path (default: current dir)")
    p_ask.add_argument("--top-k", type=int, default=5, dest="top_k")
    p_ask.set_defaults(func=cmd_ask)

    p_impact = sub.add_parser("impact", help="show what breaks if a file changes")
    p_impact.add_argument("file_path", help="relative path of the file, e.g. src/OrderService.java")
    p_impact.add_argument("--repo", default=".")
    p_impact.set_defaults(func=cmd_impact)

    p_docs = sub.add_parser("docs", help="generate markdown documentation")
    p_docs.add_argument("--repo", default=".")
    p_docs.add_argument("--out", default="docs")
    p_docs.set_defaults(func=cmd_docs)

    p_graph = sub.add_parser("graph", help="generate a Mermaid dependency graph")
    p_graph.add_argument("--repo", default=".")
    p_graph.add_argument("--out", default="architecture.md")
    p_graph.set_defaults(func=cmd_graph)

    p_stats = sub.add_parser("stats", help="print architecture summary stats")
    p_stats.add_argument("--repo", default=".")
    p_stats.set_defaults(func=cmd_stats)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
