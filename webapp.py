"""
webapp.py -- LegacyBrain AI local dashboard (zero-dependency).

Double-click run_windows.bat / run_mac_linux.command (or run:
`python webapp.py` once, if you ever need to) and it opens a browser
tab where you do everything with buttons -- scan a folder, ask
questions, check impact, generate docs/diagrams. No command typing
needed after that first double-click.
"""

import json
import mimetypes
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from legacybrain import scanner, graph as graph_mod, knowledge_base as kbmod, docgen

PORT = 8765
STATE = {"repo": None, "kb": None, "forward": None, "reverse": None, "records": None}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

ROUTES = {
    "/": "login.html",
    "/login": "login.html",
    "/dashboard": "dashboard.html",
    "/explore": "explore.html",
}


def _ensure_loaded(repo):
    repo = os.path.abspath(repo)
    kb = kbmod.load_kb(repo)
    if kb is None:
        raise ValueError("No knowledge base found for this folder. Click 'Scan Repository' first.")
    records = [entry["record"] for entry in kb["files"].values()]
    forward, reverse = graph_mod.build_dependency_graph(records)
    STATE.update(repo=repo, kb=kb, forward=forward, reverse=reverse, records=records)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep terminal quiet

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath, content_type=None):
        if not os.path.isfile(filepath):
            self.send_response(404)
            self.end_headers()
            return
        with open(filepath, "rb") as f:
            body = f.read()
        if content_type is None:
            content_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path in ROUTES:
            self._serve_file(os.path.join(STATIC_DIR, ROUTES[path]), "text/html; charset=utf-8")
            return

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            safe_path = os.path.normpath(os.path.join(STATIC_DIR, rel))
            if not safe_path.startswith(STATIC_DIR):
                self.send_response(403)
                self.end_headers()
                return
            self._serve_file(safe_path)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            payload = {}

        try:
            if path == "/api/scan":
                repo = payload.get("repo", "").strip()
                if not repo or not os.path.isdir(repo):
                    raise ValueError("Please enter a valid folder path.")
                records = scanner.scan_repo(repo)
                if not records:
                    raise ValueError("No supported source files found (.py .java .js .ts .go).")
                kb = kbmod.build_knowledge_base(records)
                kbmod.save_kb(kb, repo)
                forward, _ = graph_mod.build_dependency_graph(records)
                edges = sum(len(v) for v in forward.values())
                languages = len(set(r["language"] for r in records))
                self._send_json({
                    "message": f"Indexed {len(records)} files, {edges} dependency edges. Ready to ask questions.",
                    "files": len(records),
                    "edges": edges,
                    "languages": languages,
                })

            elif path == "/api/ask":
                _ensure_loaded(payload.get("repo", ""))
                results = kbmod.search(STATE["kb"], payload.get("question", ""), top_k=5)
                if not results:
                    msg = "No matching files found. Try different keywords."
                else:
                    lines = []
                    for i, r in enumerate(results, 1):
                        lines.append(f"{i}. {r['file']}  (confidence: {r['confidence']})")
                        if r["matched_classes"]:
                            lines.append(f"   classes:   {', '.join(r['matched_classes'])}")
                        if r["matched_functions"]:
                            lines.append(f"   functions: {', '.join(r['matched_functions'])}")
                        if r["imports"]:
                            lines.append(f"   imports:   {', '.join(r['imports'])}")
                    msg = "\n".join(lines)
                self._send_json({"message": msg})

            elif path == "/api/impact":
                _ensure_loaded(payload.get("repo", ""))
                target = payload.get("file", "").strip().replace(os.sep, "/")
                reverse = STATE["reverse"]
                if target not in reverse:
                    matches = [p for p in reverse if p.endswith(target)]
                    if len(matches) == 1:
                        target = matches[0]
                    elif len(matches) > 1:
                        raise ValueError("Ambiguous path, candidates: " + ", ".join(matches))
                    else:
                        raise ValueError(f"File not found in knowledge base: {target}")
                result = graph_mod.impact_analysis(target, reverse, STATE["forward"])
                lines = [f"Impact analysis for: {result['target']}", "",
                         f"Directly imports ({len(result['directly_imports'])}):"]
                lines += [f"  - {f}" for f in result["directly_imports"]]
                lines.append(f"\nFiles affected if this changes (total: {result['total_affected']}):")
                for depth, files in result["affected_by_depth"].items():
                    lines.append(f"  depth {depth}:")
                    lines += [f"    - {f}" for f in files]
                if result["total_affected"] == 0:
                    lines.append("  (none -- safe to change in isolation, but check test coverage)")
                self._send_json({"message": "\n".join(lines)})

            elif path == "/api/docs":
                _ensure_loaded(payload.get("repo", ""))
                out_dir = os.path.join(STATE["repo"], "docs")
                written = docgen.generate_docs(STATE["records"], out_dir)
                summary = docgen.generate_architecture_summary(STATE["records"], STATE["forward"])
                with open(os.path.join(out_dir, "ARCHITECTURE_SUMMARY.md"), "w", encoding="utf-8") as f:
                    f.write(summary)
                self._send_json({"message": f"Wrote {len(written)} file docs + architecture summary to:\n{out_dir}/"})

            elif path == "/api/graph":
                _ensure_loaded(payload.get("repo", ""))
                mermaid = graph_mod.to_mermaid(STATE["forward"], STATE["records"])
                out_path = os.path.join(STATE["repo"], "architecture.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write("# Module Dependency Graph\n\n" + mermaid + "\n")
                self._send_json({"message": f"Wrote dependency graph to:\n{out_path}\n\nOpen it in VS Code or GitHub to see the diagram rendered."})

            elif path == "/api/stats":
                _ensure_loaded(payload.get("repo", ""))
                summary = docgen.generate_architecture_summary(STATE["records"], STATE["forward"])
                self._send_json({"message": summary})

            else:
                self._send_json({"error": "unknown endpoint"}, code=404)

        except Exception as e:
            self._send_json({"error": str(e)}, code=400)


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}/"
    print(f"LegacyBrain AI dashboard running at {url}")
    print("Opening your browser... (leave this window open while you use it)")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
