# Stockfish Skills — Capability Absorption

OpenClaude-Features absorbiert und in eigenständige Python-Skills für Stockfish (Hermes Fork) umgesetzt.

## Skills

### LSP Analyzer (`stockfish-skills/lsp/`)
Live Code Intelligence + Error Checking
- `lsp_analyzer.py` — pyright type-checking + jedi code intelligence (definitions, references, hover, symbols, completions, analyze)
- Installiert: stockfish-lsp (Skill, `~/AppData/Local/hermes/skills/stockfish-lsp/`)

### Coordinator (`stockfish-skills/coordinator/`)
Parallel Worker Orchestration mit Ergebnis-Merging
- `coordinator.py` — plan (Task zerlegen), summary (Ergebnisse mergen), prompt (Koordinator-Prompt)
- Installiert: stockfish-coordinator (Skill, `~/AppData/Local/hermes/skills/stockfish-coordinator/`)

### Teams (`stockfish-skills/teams/`)
Role-Based Agent Orchestration System
- `teams.py` — 5 Rollen (explore, plan, coder, reviewer, verifier) + Team-Plan + Review-Prompt
- Installiert: stockfish-teams (Skill, `~/AppData/Local/hermes/skills/stockfish-teams/`)

## Abhängigkeiten
- Python 3.11+
- `pip install jedi pyright` (für LSP Analyzer)
- Sonst: Python stdlib only

## Tests
Alle Skills wurden getestet vor Commit.
Siehe Task T-066, T-067, T-068 im Supabase Projekt STKF.

Stand: 01.09.2026