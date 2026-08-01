"""
scanner.py
Walks a repository, detects source files, and extracts a lightweight
structural summary of each one: imports, classes, functions, docstrings,
TODO/FIXME markers, and basic line-count stats.

No external dependencies -- uses stdlib `ast` for Python (accurate) and
regex heuristics for Java / JavaScript / TypeScript / Go (best-effort,
good enough for dependency mapping and search indexing).
"""

import ast
import os
import re

SUPPORTED_EXT = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
}

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".legacybrain", "target", ".idea", ".vscode",
}

TODO_RE = re.compile(r"(TODO|FIXME|HACK|DEPRECATED)[:\s]?(.*)", re.IGNORECASE)


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _parse_python(content):
    imports, classes, functions = [], [], []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return imports, classes, functions, None

    module_doc = ast.get_docstring(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
        elif isinstance(node, ast.ClassDef):
            classes.append({"name": node.name, "doc": ast.get_docstring(node) or ""})
        elif isinstance(node, ast.FunctionDef):
            functions.append({"name": node.name, "doc": ast.get_docstring(node) or ""})
    return imports, classes, functions, module_doc


_IMPORT_PATTERNS = {
    "java": re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", re.MULTILINE),
    "javascript": re.compile(
        r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"])|(?:require\(\s*['\"]([^'\"]+)['\"]\s*\))"
    ),
    "typescript": re.compile(
        r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"])|(?:require\(\s*['\"]([^'\"]+)['\"]\s*\))"
    ),
    "go": re.compile(r'^\s*"([\w./-]+)"', re.MULTILINE),
}

_CLASS_PATTERNS = {
    "java": re.compile(r"\b(?:public|private|protected)?\s*class\s+(\w+)"),
    "javascript": re.compile(r"\bclass\s+(\w+)"),
    "typescript": re.compile(r"\bclass\s+(\w+)"),
    "go": re.compile(r"\btype\s+(\w+)\s+struct"),
}

_FUNC_PATTERNS = {
    "java": re.compile(
        r"\b(?:public|private|protected|static)+[\w<>\[\]\s]*\s(\w+)\s*\([^)]*\)\s*\{"
    ),
    "javascript": re.compile(
        r"(?:function\s+(\w+)\s*\()|(?:(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"
    ),
    "typescript": re.compile(
        r"(?:function\s+(\w+)\s*\()|(?:(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)"
    ),
    "go": re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?(\w+)\s*\("),
}


def _parse_generic(content, language):
    imports = [m for m in _IMPORT_PATTERNS[language].findall(content) if m]
    # findall on alternation patterns returns tuples; flatten
    flat_imports = []
    for m in imports:
        if isinstance(m, tuple):
            flat_imports.extend([g for g in m if g])
        else:
            flat_imports.append(m)

    classes = [{"name": n, "doc": ""} for n in _CLASS_PATTERNS[language].findall(content)]

    raw_funcs = _FUNC_PATTERNS[language].findall(content)
    functions = []
    for m in raw_funcs:
        name = m if isinstance(m, str) else next((g for g in m if g), None)
        if name:
            functions.append({"name": name, "doc": ""})

    return flat_imports, classes, functions, None


def _extract_todos(content):
    return [f"{m.group(1).upper()}: {m.group(2).strip()}" for m in TODO_RE.finditer(content)][:20]


def scan_repo(root_path):
    """Walk root_path and return a list of file records (dicts)."""
    records = []
    root_path = os.path.abspath(root_path)

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            ext = os.path.splitext(fname)[1]
            if ext not in SUPPORTED_EXT:
                continue
            language = SUPPORTED_EXT[ext]
            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, root_path)
            content = _read(full_path)
            if not content:
                continue

            if language == "python":
                imports, classes, functions, module_doc = _parse_python(content)
            else:
                imports, classes, functions, module_doc = _parse_generic(content, language)

            records.append({
                "path": rel_path.replace(os.sep, "/"),
                "language": language,
                "loc": content.count("\n") + 1,
                "imports": sorted(set(imports)),
                "classes": classes,
                "functions": functions,
                "module_doc": module_doc or "",
                "todos": _extract_todos(content),
            })

    return records
