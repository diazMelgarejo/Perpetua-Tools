"""Progressive disclosure: manifest always, full SKILL.md only when triggered."""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SKILLS_DIR = os.path.join(ROOT, "skills")
MANIFEST = os.path.join(SKILLS_DIR, "_manifest.jsonl")
FEATURES_PATH = os.path.join(ROOT, "memory", ".features.json")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from feature_flags import feature_enabled as _feature_enabled  # noqa: E402


def load_manifest():
    if not os.path.exists(MANIFEST):
        return []
    out = []
    with open(MANIFEST, encoding="utf-8") as stream:
        for line in stream:
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
    for precondition in skill.get("preconditions", []):
        if precondition.endswith("exists"):
            path = precondition.replace(" exists", "").strip()
            if not os.path.exists(os.path.join(ROOT, "..", path)):
                return False
    return True


def feature_enabled(key):
    """Backward-compatible wrapper around the shared feature reader."""
    return _feature_enabled(FEATURES_PATH, key)


def skill_enabled(skill):
    feature_flag = skill.get("feature_flag")
    return True if not feature_flag else feature_enabled(feature_flag)


def load_skill_full(name):
    base = os.path.join(SKILLS_DIR, name)
    skill_md = os.path.join(base, "SKILL.md")
    if not os.path.exists(skill_md):
        return None
    with open(skill_md, encoding="utf-8") as stream:
        content = stream.read()
    knowledge = os.path.join(base, "KNOWLEDGE.md")
    if os.path.exists(knowledge):
        with open(knowledge, encoding="utf-8") as stream:
            content += "\n\n---\n## Accumulated knowledge\n" + stream.read()
    return content


def progressive_load(user_input):
    manifest = load_manifest()
    matches = match_triggers(user_input, manifest)
    loaded = []
    for skill in matches:
        if not skill_enabled(skill):
            continue
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
