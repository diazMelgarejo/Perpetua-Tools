import os
import subprocess

branches = [
    "origin/2026-08-12-endpoint-policy-standardization",
    "origin/fix/ecc-overlay-idempotency-20260814",
    "origin/feat/tier5-asgi-harmonized-20260811",
    "origin/2026-08-14-002-gemini-consolidation-lessons",
    "origin/2026-08-14-001-coordination-board-liveness-legibility",
    "origin/docs/task5-coordination-memory-20260815"
]

def get_file_lines(ref, path):
    try:
        res = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=True)
        return [l.strip() for l in res.stdout.splitlines() if l.strip()]
    except subprocess.CalledProcessError:
        return []

def safe_merge_jsonl(path):
    print(f"Repairing {path}...")
    origin_lines = get_file_lines("origin/main", path)
    seen = set(origin_lines)
    
    final_lines = list(origin_lines)
    
    for branch in branches:
        branch_lines = get_file_lines(branch, path)
        added_count = 0
        for line in branch_lines:
            if line not in seen:
                final_lines.append(line)
                seen.add(line)
                added_count += 1
        print(f"  {branch}: added {added_count} lines")
        
    with open(path, "w") as f:
        for line in final_lines:
            f.write(line + "\n")
    print(f"Total lines: {len(final_lines)}")

safe_merge_jsonl(".agent/memory/episodic/AGENT_LEARNINGS.jsonl")
safe_merge_jsonl(".agent/memory/semantic/lessons.jsonl")

# Ensure graduated candidates are fully extracted from origin/main + branches
print("Restoring graduated candidates from origin/main...")
subprocess.run(["git", "checkout", "origin/main", "--", ".agent/memory/candidates/graduated/"], check=False)

print("Extracting graduated candidates from branches...")
for branch in branches:
    try:
        files = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch], capture_output=True, text=True, check=True).stdout.splitlines()
        for file in files:
            if file.startswith(".agent/memory/candidates/graduated/") and file.endswith(".json"):
                if not os.path.exists(file):
                    os.makedirs(os.path.dirname(file), exist_ok=True)
                    content = subprocess.run(["git", "show", f"{branch}:{file}"], capture_output=True, text=True).stdout
                    with open(file, "w") as f:
                        f.write(content)
    except Exception as e:
        pass

print("Repair complete.")
