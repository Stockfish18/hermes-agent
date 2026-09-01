#!/usr/bin/env python
"""
Stockfish Coordinator — Orchestrate parallel sub-agents with result merging.

WORKFLOW:
  Plan → Split → Spawn N Workers → Track → Collect → Merge → Verify

Usage:
  python coordinator.py plan "complex task description"
    -> Splits task into N sub-tasks, prints plan

  python coordinator.py summary "worker1:result; worker2:result"
    -> Merges worker results into a synthesized summary
"""

import json, sys, os
from pathlib import Path
from datetime import datetime


def decompose_task(task_description: str, max_workers: int = 4) -> dict:
    """
    Given a complex task description, decompose into parallel sub-tasks.
    Returns a plan dict with sub-tasks and their deps.
    """
    task = task_description.strip()

    # Heuristic decomposition patterns
    lines = task.split("\n")
    words = task.split()

    # Count potential sub-tasks by keywords
    sub_task_markers = [
        "backend", "frontend", "api", "database", "auth", "ui",
        "testing", "docs", "deploy", "config", "security", "refactor",
        "research", "implement", "verify"
    ]

    detected = [w for w in words if w.lower().rstrip(".,;:!?") in sub_task_markers]

    return {
        "original": task,
        "word_count": len(words),
        "detected_domains": detected,
        "suggested_workers": min(max(len(detected), 2), max_workers),
        "timestamp": datetime.now().isoformat()
    }


def synthesize_results(worker_results: list[dict]) -> dict:
    """
    Merge N worker results into a coordinated summary.
    Each result: {"id": "agent-X", "goal": "...", "summary": "...", "status": "ok|fail"}
    """
    ok_results = [r for r in worker_results if r.get("status") == "ok"]
    fail_results = [r for r in worker_results if r.get("status") != "ok"]

    merged = {
        "total": len(worker_results),
        "succeeded": len(ok_results),
        "failed": len(fail_results),
        "verdict": "ALL_OK" if not fail_results else f"{len(fail_results)} FAILED" if ok_results else "ALL_FAILED",
        "synthesis": "",
    }

    if ok_results:
        merged["synthesis"] = " | ".join(
            f"[{r['id']}] {r.get('goal', '')[:60]}: {r.get('summary', '')[:120]}"
            for r in ok_results
        )

    if fail_results:
        merged["failures"] = [
            {"id": r.get("id"), "goal": r.get("goal"), "error": r.get("error", "unknown")}
            for r in fail_results
        ]

    return merged


def generate_coordinator_prompt(task: str, sub_tasks: list[dict]) -> str:
    """Generate the coordinator system prompt for Stockfish."""
    prompt = f"""You are Stockfish, coordinating {len(sub_tasks)} parallel workers.

ORIGINAL TASK: {task}

SUB-TASKS:
"""
    for i, st in enumerate(sub_tasks, 1):
        deps = f" [depends_on: {st.get('depends_on', 'none')}]" if st.get('depends_on') else ""
        prompt += f"  {i}. {st['goal']}{deps}\n"

    prompt += """
PROTOCOL:
1. Spawn all independent workers FIRST via delegate_task
2. Wait for results (they arrive asynchronously)
3. Spawn dependent workers after prerequisites complete
4. Merge results: synthesize findings, flag conflicts
5. Report: VERDICT + summary per worker + merged conclusion

RULES:
- Do NOT predict worker results — wait for actual completion
- If one worker fails, continue others and note partial failure
- Never delegate what you can answer directly
"""
    return prompt


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    op = sys.argv[1]

    if op == "plan":
        task = sys.argv[2] if len(sys.argv) > 2 else "No task provided"
        plan = decompose_task(task)
        print(json.dumps(plan, indent=2))

    elif op == "summary":
        if len(sys.argv) < 3:
            print("Usage: coordinator.py summary 'worker results JSON array'")
            sys.exit(1)
        try:
            results = json.loads(sys.argv[2])
            summary = synthesize_results(results)
            print(json.dumps(summary, indent=2))
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON: {e}"}))

    elif op == "prompt":
        task = sys.argv[2] if len(sys.argv) > 2 else ""
        sub_tasks = []
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--sub":
                goal = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
                dep = sys.argv[i + 2] if i + 2 < len(sys.argv) and sys.argv[i + 2] != "--sub" else ""
                sub_tasks.append({"goal": goal, "depends_on": dep if dep else None})
                i += 3 if dep else 2
            else:
                i += 1
        print(generate_coordinator_prompt(task, sub_tasks))

    else:
        print(json.dumps({"error": f"Unknown operation: {op}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()