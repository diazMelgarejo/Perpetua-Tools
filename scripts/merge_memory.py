import json
import subprocess
import os
import glob

branches = [
    "origin/2026-08-12-endpoint-policy-standardization",
    "origin/fix/ecc-overlay-idempotency-20260814",
    "origin/feat/tier5-asgi-harmonized-20260811",
    "origin/2026-08-14-002-gemini-consolidation-lessons",
    "origin/2026-08-14-001-coordination-board-liveness-legibility",
    "origin/docs/task5-coordination-memory-20260815" # just in case
]

def get_file_from_branch(branch, path):
    try:
        result = subprocess.run(["git", "show", f"{branch}:{path}"], capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError:
        return []

def union_jsonl(local_path, target_key):
    if not os.path.exists(local_path):
        open(local_path, 'a').close()
        
    with open(local_path, "r") as f:
        local_lines = [l.strip() for l in f if l.strip()]

    seen_keys = set()
    deduped_lines = []

    for line in local_lines:
        try:
            data = json.loads(line)
            key = data.get(target_key)
            if target_key == "run_id" and "source" in data:
                key = data["source"].get("run_id")
                
            if key:
                if key in seen_keys: continue
                seen_keys.add(key)
            deduped_lines.append(line)
        except:
            deduped_lines.append(line)

    for branch in branches:
        branch_lines = get_file_from_branch(branch, local_path)
        for line in branch_lines:
            line = line.strip()
            if not line: continue
            try:
                data = json.loads(line)
                key = data.get(target_key)
                if target_key == "run_id" and "source" in data:
                    key = data["source"].get("run_id")
                    
                if key:
                    if key in seen_keys: continue
                    seen_keys.add(key)
                deduped_lines.append(line)
            except:
                deduped_lines.append(line)

    with open(local_path, "w") as f:
        for line in deduped_lines:
            f.write(line + "\n")

print("Unioning AGENT_LEARNINGS.jsonl...")
union_jsonl(".agent/memory/episodic/AGENT_LEARNINGS.jsonl", "run_id")

print("Unioning lessons.jsonl...")
union_jsonl(".agent/memory/semantic/lessons.jsonl", "id")

# Fetch all graduated JSON files from branches
print("Extracting graduated candidate JSONs...")
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
                    print(f"Extracted {file} from {branch}")
    except:
        pass

print("Done. Please regenerate LESSONS.md if needed.")
