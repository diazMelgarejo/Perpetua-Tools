"""Progressive disclosure: manifest always, full SKILL.md only when triggered."""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
SKILLS_DIR = os.path.join(ROOT, "skills")
MANIFEST = os.path.join(SKILLS_DIR, "_manifest.jsonl")


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    out = []
    for line in open(MANIFEST):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def match_triggers(user_input, manifest):
    matches = []
    text = user_input.lower()
    for skill in manifest:
        for trigger in skill.get("triggers", []):
            if trigger.lower() in text:
                matches.append(skill)
                break
    return matches


def check_preconditions(skill):
    for pre in skill.get("preconditions", []):
        if pre.endswith("exists"):
            path = pre.replace(" exists", "").strip()
            if not os.path.exists(os.path.join(ROOT, "..", path)):
                return False
    return True


def load_skill_full(name):
    base = os.path.join(SKILLS_DIR, name)
    skill_md = os.path.join(base, "SKILL.md")
    if not os.path.exists(skill_md):
        return None
    content = open(skill_md).read()
    knowledge = os.path.join(base, "KNOWLEDGE.md")
    if os.path.exists(knowledge):
        content += "\n\n---\n## Accumulated knowledge\n" + open(knowledge).read()
    return content


def progressive_load(user_input):
    manifest = load_manifest()
    matches = match_triggers(user_input, manifest)
    loaded = []
    for skill in matches:
        if not check_preconditions(skill):
            continue
        content = load_skill_full(skill["name"])
        if not content:
            continue
        loaded.append({
            "name": skill["name"],
            "constraints": skill.get("constraints", []),
            "content": content,
        })
    return loaded
