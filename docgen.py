"""
docgen.py
Generates markdown documentation for each scanned file, plus a
project-level architecture summary, from scanner records.
"""

import os


def _file_doc(record):
    lines = [f"# {record['path']}", "", f"**Language:** {record['language']}  ",
              f"**Lines of code:** {record['loc']}", ""]

    if record.get("module_doc"):
        lines += ["## Description", record["module_doc"], ""]

    if record.get("classes"):
        lines.append("## Classes")
        for c in record["classes"]:
            lines.append(f"- **{c['name']}**" + (f" -- {c['doc']}" if c.get("doc") else ""))
        lines.append("")

    if record.get("functions"):
        lines.append("## Functions")
        for fn in record["functions"]:
            lines.append(f"- `{fn['name']}()`" + (f" -- {fn['doc']}" if fn.get("doc") else ""))
        lines.append("")

    if record.get("imports"):
        lines.append("## Dependencies")
        for imp in record["imports"]:
            lines.append(f"- {imp}")
        lines.append("")

    if record.get("todos"):
        lines.append("## Open Issues / TODOs")
        for t in record["todos"]:
            lines.append(f"- {t}")
        lines.append("")

    return "\n".join(lines)


def generate_docs(records, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for r in records:
        safe_name = r["path"].replace("/", "__") + ".md"
        out_path = os.path.join(out_dir, safe_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(_file_doc(r))
        written.append(out_path)
    return written


def generate_architecture_summary(records, forward_graph):
    total_files = len(records)
    total_loc = sum(r["loc"] for r in records)
    by_language = {}
    for r in records:
        by_language[r["language"]] = by_language.get(r["language"], 0) + 1

    todos = [(r["path"], t) for r in records for t in r.get("todos", [])]
    most_depended_on = sorted(
        records,
        key=lambda r: sum(1 for f, deps in forward_graph.items() if r["path"] in deps),
        reverse=True,
    )[:5]

    lines = ["# Architecture Summary", "",
              f"- **Total files scanned:** {total_files}",
              f"- **Total lines of code:** {total_loc}",
              "- **Languages:** " + ", ".join(f"{lang} ({n})" for lang, n in by_language.items()),
              ""]

    lines.append("## Most Depended-On Files (high-risk to change)")
    for r in most_depended_on:
        dep_count = sum(1 for f, deps in forward_graph.items() if r["path"] in deps)
        lines.append(f"- `{r['path']}` -- depended on by {dep_count} file(s)")
    lines.append("")

    if todos:
        lines.append(f"## Open TODO / FIXME markers ({len(todos)} found)")
        for path, t in todos[:30]:
            lines.append(f"- `{path}`: {t}")
        lines.append("")

    return "\n".join(lines)
