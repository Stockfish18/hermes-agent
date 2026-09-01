#!/usr/bin/env python
"""
Stockfish LSP Analyzer — Live Code Intelligence + Error Checking

Usage:
  python lsp_analyzer.py check FILE                        # Pyright error check
  python lsp_analyzer.py check FILE --json                  # JSON output
  python lsp_analyzer.py definitions FILE LINE COL          # Jedi goto_definitions
  python lsp_analyzer.py references FILE LINE COL           # Jedi find_references
  python lsp_analyzer.py hover FILE LINE COL                # Jedi hover info
  python lsp_analyzer.py symbols FILE                       # Jedi document symbols
  python lsp_analyzer.py completions FILE LINE COL          # Jedi completions
  python lsp_analyzer.py analyze FILE                       # Full analysis
"""

import json, os, sys
from pathlib import Path

ANALYZER_DIR = Path(__file__).parent.resolve()
PROJECT_DIRS = [
    Path.home() / "AppData/Local/hermes/hermes-agent",
    Path.home() / "hermes-agent",
    Path.home() / "Dokumente/dreoss",
    Path.home() / "Dokumente/landing",
    Path.home() / "openclaude",
]

def find_project_root(file_path):
    """Walk up from file to find closest project root."""
    f = Path(file_path).resolve()
    for parent in [f] + list(f.parents):
        if (parent / ".git").exists():
            return parent
        if (parent / "pyproject.toml").exists() or (parent / "setup.py").exists() or (parent / "setup.cfg").exists():
            return parent
    # Default: try known project dirs
    for pdir in PROJECT_DIRS:
        try:
            f.relative_to(pdir)
            return pdir
        except ValueError:
            continue
    return f.parent


def pyright_check(file_path, as_json=False):
    """Run pyright type checker on a file."""
    f = Path(file_path)
    if not f.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    project_root = find_project_root(file_path)

    # Build pyright command
    cmd = f'cd "{project_root}" && pyright --outputjson "{f}" 2>&1'
    result = os.popen(f'bash -c "{cmd}"').read().strip()

    # Handle no output / parse errors
    if not result:
        return {"status": "ok", "diagnostics": [], "summary": {"errors": 0, "warnings": 0, "info": 0}}

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        # Plain text output fallback
        return {"status": "ok", "raw_output": result[:2000], "diagnostics": [], "summary": {"errors": 0, "warnings": 0, "info": 0, "note": "JSON parse failed, showing raw"}}

    if as_json:
        return data

    diagnostics = data.get("generalDiagnostics", [])
    summary = {"errors": 0, "warnings": 0, "info": 0}
    categorized = {"errors": [], "warnings": [], "info": []}

    for d in diagnostics:
        sev = d.get("severity", "information").lower()
        entry = {
            "line": d.get("range", {}).get("start", {}).get("line", 0),
            "column": d.get("range", {}).get("start", {}).get("character", 0),
            "message": d.get("message", ""),
            "rule": d.get("rule", ""),
        }
        if "error" in sev:
            summary["errors"] += 1
            categorized["errors"].append(entry)
        elif "warning" in sev:
            summary["warnings"] += 1
            categorized["warnings"].append(entry)
        else:
            summary["info"] += 1
            categorized["info"].append(entry)

    return {"status": "ok", "diagnostics": categorized, "summary": summary, "file": str(f)}


def jedi_query(file_path, line, col, operation):
    """Use Jedi for code intelligence operations."""
    f = Path(file_path)
    if not f.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    code = f.read_text(encoding="utf-8", errors="replace")
    project = find_project_root(file_path)

    import jedi
    script = jedi.Script(code, path=str(f), project=str(project))

    results = {
        "definitions": lambda: [
            {"name": d.name, "line": d.line, "column": d.column, "type": d.type,
             "module_path": d.module_path, "description": d.description,
             "full_name": d.full_name, "in_builtin": d.in_builtin}
            for d in script.goto_definitions(line, col)
        ],
        "references": lambda: [
            {"line": r.line, "column": r.column, "module_path": r.module_path}
            for r in script.get_references(line, col)
        ],
        "hover": lambda: [
            {"description": d.description, "type": d.type, "docstring": d.docstring()[:500] if d.docstring() else ""}
            for d in script.goto_definitions(line, col)
        ],
        "symbols": lambda: [
            {"name": n.name, "line": n.line, "column": n.column, "type": n.type}
            for n in script.get_names(all_scopes=True, definitions=True)
        ],
        "completions": lambda: [
            {"name": c.name, "type": c.type, "description": c.description, "docstring": c.docstring()[:300] if c.docstring() else ""}
            for c in script.complete(line, col)
        ],
    }

    if operation in results:
        return {"status": "ok", "operation": operation, "results": results[operation](), "file": str(f)}
    return {"status": "error", "message": f"Unknown operation: {operation}"}


def document_symbols(file_path):
    """Extract all symbols from a file using Jedi + regex fallback."""
    f = Path(file_path)
    if not f.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    code = f.read_text(encoding="utf-8", errors="replace")

    try:
        import jedi
        script = jedi.Script(code, path=str(f))
        names = script.get_names(all_scopes=True, definitions=True)
        symbols = [
            {"name": n.name, "line": n.line, "type": n.type, "full_name": n.full_name}
            for n in names
        ]
        return {"status": "ok", "symbols": symbols, "count": len(symbols), "file": str(f)}
    except Exception as e:
        pass

    # Regex fallback for Python
    import re
    patterns = [
        (r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", "function"),
        (r"^\s*(?:async\s+)?class\s+(\w+)", "class"),
        (r"^\s*(\w+)\s*=\s*(?:dataclass|TypedDict)", "dataclass"),
        (r"@[\w.]+\s*\n\s*def\s+(\w+)", "decorated_function"),
    ]
    symbols = []
    seen = set()
    for line_no, line in enumerate(code.split("\n"), 1):
        for pat, sym_type in patterns:
            m = re.match(pat, line)
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                symbols.append({"name": m.group(1), "line": line_no, "type": sym_type})
    return {"status": "ok", "symbols": symbols, "count": len(symbols), "file": str(f), "note": "regex fallback"}


def full_analysis(file_path):
    """Combine error check + symbol extraction into one report."""
    errors = pyright_check(file_path)
    syms = document_symbols(file_path)
    f = Path(file_path)
    code = f.read_text(encoding="utf-8", errors="replace") if f.exists() else ""
    lines = len(code.split("\n")) if code else 0
    loc = sum(1 for l in code.split("\n") if l.strip() and not l.strip().startswith("#")) if code else 0

    verdict = "CLEAN"
    if errors.get("summary", {}).get("errors", 0) > 0:
        verdict = "ERRORS"
    elif errors.get("summary", {}).get("warnings", 0) > 0:
        verdict = "WARNINGS"

    return {
        "verdict": verdict,
        "file": str(f),
        "lines": lines,
        "loc": loc,
        "errors": errors,
        "symbols": syms,
        "summary": f"{verdict}: {errors.get('summary', {}).get('errors', 0)} errors, {errors.get('summary', {}).get('warnings', 0)} warnings, {syms.get('count', 0)} symbols"
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    op = sys.argv[1]
    fpath = sys.argv[2]
    as_json = "--json" in sys.argv

    if op == "check":
        result = pyright_check(fpath, as_json=as_json)
        print(json.dumps(result, indent=2, default=str))
    elif op == "definitions":
        line, col = int(sys.argv[3]), int(sys.argv[4])
        result = jedi_query(fpath, line, col, "definitions")
        print(json.dumps(result, indent=2, default=str))
    elif op == "references":
        line, col = int(sys.argv[3]), int(sys.argv[4])
        result = jedi_query(fpath, line, col, "references")
        print(json.dumps(result, indent=2, default=str))
    elif op == "hover":
        line, col = int(sys.argv[3]), int(sys.argv[4])
        result = jedi_query(fpath, line, col, "hover")
        print(json.dumps(result, indent=2, default=str))
    elif op == "symbols":
        result = document_symbols(fpath)
        print(json.dumps(result, indent=2, default=str))
    elif op == "completions":
        line, col = int(sys.argv[3]), int(sys.argv[4])
        result = jedi_query(fpath, line, col, "completions")
        print(json.dumps(result, indent=2, default=str))
    elif op == "analyze":
        result = full_analysis(fpath)
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps({"status": "error", "message": f"Unknown operation: {op}"}))
        sys.exit(1)