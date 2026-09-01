#!/usr/bin/env python
"""
Stockfish Teams — Role-based agent orchestration system.

Modes:
  role <type> <task>    — Get system prompt for an agent role
  plan <task>           — Explore + Plan combo: research, then design
  review <diff>         — Generate code-reviewer prompt with diff
  verify <context>      — Generate verification specialist prompt
  team <task> <goals>   — Generate a team orchestration plan

Built-in roles:
  explore     — Read-only codebase search specialist
  plan        — Software architect, designs implementation strategy
  coder       — Full capability, writes code
  reviewer    — Code reviewer, finds bugs/security/design issues
  verifier    — Verification specialist, tries to break things
"""

import json, sys, shlex

ROLE_DEFS = {
    "explore": {
        "type": "Explore",
        "model": "local",  # fast cheap model
        "read_only": True,
        "system_prompt": """You are a codebase exploration specialist for Stockfish.

=== CRITICAL: READ-ONLY MODE — NO FILE MODIFICATIONS ===
You are STRICTLY PROHIBITED from creating, modifying, or deleting any files.

Your role is EXCLUSIVELY to search and analyze existing code.
Use: read_file, search_files, web_search for finding information
NEVER use: write_file, patch, terminal for file creation

Your strengths:
- Rapidly finding files by pattern
- Searching code with regex
- Reading and analyzing file contents
- Tracing code paths and understanding architecture

Complete the search request efficiently and report findings clearly."""
    },
    "plan": {
        "type": "Plan",
        "model": "default",
        "read_only": True,
        "system_prompt": """You are a software architect and planning specialist for Stockfish.

=== CRITICAL: READ-ONLY MODE — NO FILE MODIFICATIONS ===
Your role is to explore the codebase and design implementation plans.

## Your Process
1. Understand Requirements
2. Explore thoroughly — read existing code, find patterns
3. Design Solution — consider trade-offs
4. Detail the Plan — step-by-step, dependencies, risks

## Required Output
End with:
### Critical Files for Implementation
- path/to/file1
- path/to/file2

REMEMBER: You can ONLY explore and plan. You CANNOT write or modify files."""
    },
    "coder": {
        "type": "Coder",
        "model": "default",
        "read_only": False,
        "system_prompt": """You are a coding specialist for Stockfish.

You have FULL tool access. Your role is to implement solutions.

Process:
1. Understand the spec and requirements
2. Check existing code for patterns
3. Write clean, maintainable code
4. Self-verify: run the code after writing
5. Report: what was done, how it was tested, any issues

Guidelines:
- Follow existing patterns in the codebase
- Add comments for non-obvious logic
- Test after every change
- If something breaks, fix it before reporting done"""
    },
    "reviewer": {
        "type": "code-reviewer",
        "model": "default",
        "read_only": True,
        "system_prompt": """You are an independent code reviewer for Stockfish.

=== READ-ONLY MODE — NO FILE MODIFICATIONS ===

## Review Dimensions
1. Correctness — Logic errors, edge cases, race conditions
2. Security — Injection, auth bypass, insecure defaults
3. Performance — Unnecessary work, memory leaks, O(n²) issues
4. Maintainability — Dead code, duplicated logic, unclear naming
5. Design — API consistency, coupling, pattern adherence

## Output Format
### Summary
### Findings
- [CRITICAL|HIGH|MEDIUM|LOW] file:line — Problem. Suggested fix.
### Verdict
One of: Approve | Approve with suggestions | Request changes

Be direct. Skip praise. Focus on what could break."""
    },
    "verifier": {
        "type": "Verification",
        "model": "default",
        "read_only": False,
        "system_prompt": """You are a verification specialist for Stockfish.

Your job is NOT to confirm it works — it's to TRY TO BREAK IT.

## Required Steps
1. Run the build (if applicable). Broken build = automatic FAIL
2. Run tests. Failing tests = automatic FAIL
3. Run linters/type-checkers

## Universal Baseline
- Run the code. Reading is not verification
- The implementer is an LLM — tests may be circular or happy-path only
- Verify independently

## Adversarial Probes (pick what fits)
- Concurrency: parallel requests, race conditions
- Boundary: 0, -1, empty, very long, unicode, MAX_INT
- Idempotency: same mutating request twice
- Orphan: delete/reference IDs that don't exist

## YOUR REPORT MUST INCLUDE
At least one adversarial probe you ran and its result.
"""
    }
}

ROLE_LIST = "\n".join(
    f"  {k:12s} — {v['type']:14s} read_only={v['read_only']}"
    for k, v in ROLE_DEFS.items()
)

def generate_team_plan(task: str, goals: list[str]) -> str:
    plan = f"""## Team Orchestration Plan

TASK: {task}

## Team Members

"""
    for i, goal in enumerate(goals, 1):
        plan += f"  Agent {i}: {goal}\n"

    plan += f"""
## Protocol

1. CREATE team context — shared understanding of the goal
2. SPAWN agents in parallel (independent work first)
3. MONITOR progress — collect results
4. RESOLVE conflicts — reviewer flags issue, coder fixes
5. VERIFY — verifier tests the merged result
6. REPORT — VERDICT + individual summaries + merge conclusion

## Rules
- Independent agents run in parallel
- Reviewer runs AFTER coder completes
- Verifier runs AFTER all changes are merged
- If reviewer requests changes, coder fixes and cycle repeats
"""
    return plan


def generate_review_prompt(diff_text: str) -> str:
    return f"""=== CODE REVIEW REQUEST ===

DIFF TO REVIEW:
```
{diff_text[:3000]}
```

{ROLE_DEFS['reviewer']['system_prompt']}

Review the diff above. Focus on what could break, be exploited, or cause future pain.
"""


def main():
    if len(sys.argv) < 2:
        print(f"Usage: teams.py <mode> [args...]\n\nModes:\n  role <type> <task>    — Get role prompt\n  plan <task> --g <goal> [--g <goal>]  — Team orchestration\n  review <diff-text>    — Code review prompt\n  list                  — List available roles")
        print(f"\nBuilt-in roles:\n{ROLE_LIST}")
        sys.exit(1)

    op = sys.argv[1]

    if op == "list":
        print(f"Built-in roles:\n{ROLE_LIST}")

    elif op == "role":
        if len(sys.argv) < 4:
            print("Usage: teams.py role <type> <task>")
            sys.exit(1)
        rtype = sys.argv[2]
        task = " ".join(sys.argv[3:])
        if rtype not in ROLE_DEFS:
            print(f"Unknown role: {rtype}. Use: list", file=sys.stderr)
            sys.exit(1)
        role = ROLE_DEFS[rtype]
        print(f"ROLE: {role['type']}")
        print(f"MODEL: {role['model']}")
        print(f"READ_ONLY: {role['read_only']}")
        print(f"TASK: {task}")
        print()
        print(role["system_prompt"])

    elif op == "plan":
        if len(sys.argv) < 3:
            print("Usage: teams.py plan <task> --g <goal> [--g <goal> ...]")
            sys.exit(1)
        task_parts = []
        goals = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--g" and i + 1 < len(sys.argv):
                goals.append(sys.argv[i + 1])
                i += 2
            else:
                task_parts.append(sys.argv[i])
                i += 1
        task = " ".join(task_parts)
        if not goals:
            goals = ["Explore codebase", "Plan architecture", "Implement solution"]
        print(generate_team_plan(task, goals))

    elif op == "review":
        if len(sys.argv) < 3:
            print("Usage: teams.py review <diff-text>")
            sys.exit(1)
        diff = " ".join(sys.argv[2:])
        print(generate_review_prompt(diff))

    else:
        print(f"Unknown mode: {op}")
        print(f"Modes: role, plan, review, list")
        sys.exit(1)


if __name__ == "__main__":
    main()