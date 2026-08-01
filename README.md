# LegacyBrain AI (No-Command-Line Prototype)

A runnable, dependency-free proof-of-concept of the LegacyBrain AI idea:
point it at a codebase and it builds a searchable knowledge base,
a dependency graph, impact analysis, and auto-generated docs — no API
key, no internet connection, and (via the dashboard below) no typing
commands required.

## Easiest way to run it — double-click, no terminal

1. Make sure Python 3.8+ is installed on your machine (most Mac/Linux
   computers already have it; Windows: install from python.org and
   check "Add python.exe to PATH" during setup — this is the only
   one-time setup step, and it uses the installer, not a terminal).
2. **Windows:** double-click `Start_LegacyBrain_Windows.bat`
   **Mac/Linux:** double-click `Start_LegacyBrain_Mac_Linux.command`
   (on Mac, if it opens in a text editor instead of running, right-click
   it → Open With → Terminal the first time)
3. A browser tab opens automatically at `http://127.0.0.1:8765/` with
   a dashboard: paste in your repo folder path, click **Scan
   Repository**, then use the Ask / Impact / Docs / Graph buttons —
   everything after that first double-click is just clicking buttons
   and typing into text boxes on the page.

The small window that pops up in the background is just the local
server powering the page — leave it open while you use the dashboard,
close it when you're done.

---

## Terminal version (optional, for developers)

If you'd rather use the command line, the same functionality is also
available as a CLI — see below.

This is a **static-analysis prototype**. It implements the mechanics of
every feature in the pitch (repository intelligence, knowledge graph,
NL search, impact analysis, auto-docs, architecture diagrams) using
Python's `ast` module + regex heuristics instead of an LLM, so it's
free to run and works fully offline. It's structured so an LLM call
(OpenAI, Claude, etc.) can be dropped in later to turn the raw search
results into fluent natural-language answers — see "Extending with a
real LLM" below.

## Requirements
- Python 3.8+ (stdlib only — no `pip install` needed)

## Quick Start

```bash
# 1. Scan a repository (any local folder — your own project, or a client repo)
python -m legacybrain.cli scan /path/to/your/repo

# 2. Ask natural-language questions about it
python -m legacybrain.cli ask "where is payment calculated" --repo /path/to/your/repo

# 3. Check the blast radius before changing a file
python -m legacybrain.cli impact src/OrderService.java --repo /path/to/your/repo

# 4. Generate documentation
python -m legacybrain.cli docs --repo /path/to/your/repo

# 5. Generate a Mermaid dependency diagram
python -m legacybrain.cli graph --repo /path/to/your/repo

# 6. Print a quick architecture summary
python -m legacybrain.cli stats --repo /path/to/your/repo
```

Try it immediately on the bundled `sample_repo/` (a tiny 3-file mock
e-commerce backend with the exact example questions from the pitch —
"where is payment calculated", "which API updates inventory", "where
is GST implemented"):

```bash
python -m legacybrain.cli scan sample_repo
python -m legacybrain.cli ask "where is payment calculated" --repo sample_repo
python -m legacybrain.cli impact src/tax_utils.py --repo sample_repo
```

## What each command does

| Command  | Maps to pitch feature          | What it does |
|----------|--------------------------------|--------------|
| `scan`   | Repository Intelligence        | Walks the repo, parses `.py .java .js .jsx .ts .tsx .go` files, extracts imports/classes/functions/docstrings/TODOs, saves a knowledge base to `.legacybrain/kb.json` |
| `ask`    | NL Repository Search           | TF-IDF-style keyword search over the knowledge base; returns matching files, classes, functions, and a confidence score |
| `impact` | Impact Analysis                | Builds a reverse dependency graph and BFS's outward from a file to show every file that would be affected by a change to it |
| `docs`   | Auto Documentation             | Generates one Markdown file per source file plus an `ARCHITECTURE_SUMMARY.md` |
| `graph`  | Architecture Visualization     | Emits a Mermaid `flowchart` of file-level dependencies (renders natively on GitHub / VS Code) |
| `stats`  | Modernization Advisor (partial)| Prints LOC, language breakdown, most-depended-on ("high blast radius") files, and all TODO/FIXME markers found |

## Project layout

```
legacybrain/
  legacybrain/
    scanner.py         # repo walking + per-file parsing (ast for Python, regex for others)
    graph.py           # dependency graph construction + impact analysis + Mermaid export
    knowledge_base.py  # TF-IDF-style index + search, persisted to .legacybrain/kb.json
    docgen.py          # markdown doc + architecture summary generation
    cli.py             # argparse CLI wiring it all together
  sample_repo/         # tiny demo repo to try commands against immediately
```

## Known limitations (be upfront about these if presenting)
- Dependency resolution matches imports to files by name, so two files
  with the same name in different languages/folders can occasionally
  cross-match — fine for a prototype, would need proper per-language
  resolvers (e.g. Java package paths, JS relative paths) for production.
- `ask` uses lexical (keyword) search, not semantic embeddings — it
  won't catch a query like "how do we bill customers" for code that
  never uses the word "bill". Swapping in an embedding model is the
  natural next step (see below).
- Regex-based parsing for Java/JS/TS/Go is best-effort, not a full
  parser — good enough for dependency mapping and search, not for
  refactoring safety guarantees.

## Extending with a real LLM
The architecture in the original pitch (GitHub repo → parser →
dependency analyzer → knowledge graph → embeddings/vector DB → LLM →
dashboard) maps directly onto this code:

- `scanner.py` = "Repository Parser"
- `graph.py` = "Dependency Analyzer" + part of "Knowledge Graph Builder"
- `knowledge_base.py` = "Knowledge Graph Builder" + "Embedding + Vector Database" (currently TF-IDF instead of real embeddings)
- `cli.py`'s `cmd_ask` = where you'd call an LLM: take `kbmod.search()`'s
  top results, stuff their file contents into a prompt, and ask
  ChatGPT/Codex/Claude to synthesize a natural-language answer with
  citations — instead of just printing the raw matches.
- A "Web Dashboard" (React + FastAPI, as in the original stack) can sit
  in front of these same modules — `scanner`, `graph`, `knowledge_base`,
  and `docgen` are already plain importable Python functions with no
  CLI-specific coupling.
