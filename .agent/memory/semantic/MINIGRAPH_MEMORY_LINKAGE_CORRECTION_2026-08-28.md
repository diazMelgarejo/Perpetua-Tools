# MiniGraph memory linkage correction — 2026-08-28

The first graduated candidate created during the final MiniGraph reconciliation,
`6f2a3c1d9e47.json`, used an unsupported ad-hoc `supersedes` key.

Per the canonical `perpetua-memory` skill, graduated candidate JSON must link to
prior lessons with:

```json
"related_lesson_ids": ["lesson_<id>"]
```

and existing graduated records must not be rewritten in place.

Therefore the corrected canonical linkage record is:

```text
.agent/memory/candidates/graduated/9c4f8a7d21be.json
```

It links the final architecture to:

- `lesson_e0ff7f2d6717`;
- `lesson_1079e8c74f20`;
- `lesson_4a711949b3ed`.

Treat `6f2a3c1d9e47.json` as preserved process evidence of the metadata mistake,
not as the canonical linkage record. Do not edit or delete it in place.
