"""
knowledge_base.py
Turns scanner records into a persisted JSON knowledge base and provides
a lightweight, dependency-free natural-language search over it (TF-IDF
style scoring implemented from scratch -- no sklearn/numpy required).
"""

import json
import math
import os
import re
from collections import Counter

KB_DIR = ".legacybrain"
KB_FILE = "kb.json"

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,}")


def _tokenize(text):
    # split camelCase / snake_case into separate words, lowercase everything
    words = _WORD_RE.findall(text)
    tokens = []
    for w in words:
        sub = re.sub(r"(?<!^)(?=[A-Z])", " ", w).split()
        tokens.extend(s.lower() for s in sub if len(s) > 1)
    return tokens


def _searchable_text(record):
    parts = [record["path"], record.get("module_doc", "")]
    for c in record.get("classes", []):
        parts.append(c["name"])
        parts.append(c.get("doc", ""))
    for fn in record.get("functions", []):
        parts.append(fn["name"])
        parts.append(fn.get("doc", ""))
    parts.extend(record.get("imports", []))
    return " ".join(parts)


def build_knowledge_base(records):
    kb = {"files": {}}
    for r in records:
        text = _searchable_text(r)
        kb["files"][r["path"]] = {
            "record": r,
            "tokens": _tokenize(text),
        }
    return kb


def save_kb(kb, root_path):
    out_dir = os.path.join(root_path, KB_DIR)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, KB_FILE), "w", encoding="utf-8") as f:
        json.dump(kb, f)
    return os.path.join(out_dir, KB_FILE)


def load_kb(root_path):
    path = os.path.join(root_path, KB_DIR, KB_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_idf(kb):
    n_docs = len(kb["files"])
    df = Counter()
    for entry in kb["files"].values():
        for tok in set(entry["tokens"]):
            df[tok] += 1
    idf = {tok: math.log((n_docs + 1) / (freq + 1)) + 1 for tok, freq in df.items()}
    return idf


def search(kb, query, top_k=5):
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    idf = _build_idf(kb)
    scored = []

    for path, entry in kb["files"].items():
        tf = Counter(entry["tokens"])
        score = 0.0
        for qt in q_tokens:
            if qt in tf:
                score += (1 + math.log(tf[qt])) * idf.get(qt, 1.0)
        if score > 0:
            scored.append((score, path, entry["record"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, path, record in scored[:top_k]:
        matched_classes = [c["name"] for c in record.get("classes", [])
                            if any(qt in c["name"].lower() for qt in q_tokens)]
        matched_functions = [f["name"] for f in record.get("functions", [])
                              if any(qt in f["name"].lower() for qt in q_tokens)]
        results.append({
            "file": path,
            "language": record["language"],
            "confidence": round(min(score / (len(q_tokens) * 3), 1.0), 2),
            "matched_classes": matched_classes,
            "matched_functions": matched_functions,
            "imports": record.get("imports", [])[:8],
        })
    return results
