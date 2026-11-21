"""Append provenance-bearing canonical identities without promoting claims."""
import argparse
import hashlib
import json
import logging
import re
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'memory'))
from render_lessons import _locked_jsonl, _append_lesson_unlocked, render_lessons

_LOG = logging.getLogger(__name__)


def migrate(ids: list[str], semantic: Path, candidates: Path) -> list[dict]:
    """Transfer accepted decisions; a partial append is safe to retry after validation."""
    semantic, candidates = Path(semantic), Path(candidates)
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate candidate IDs')
    planned = []
    with _locked_jsonl(str(semantic / 'lessons.jsonl')) as stream:
        stream.seek(0)
        raw = stream.read()
        latest = {}
        raw_latest = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get('id'):
                latest[row['id']] = row
                raw_latest[row['id']] = line.encode('utf8')
        retired = {row.get('supersedes') for row in latest.values()
                   if row.get('status') == 'accepted' and row.get('supersedes')}
        for cid in ids:
            if not re.fullmatch(r'[0-9a-f]{12}', cid):
                raise ValueError('invalid candidate ID')
            candidate_bytes = (candidates / (cid + '.json')).read_bytes()
            candidate = json.loads(candidate_bytes)
            original = latest.get(cid)
            if candidate.get('id') != cid or candidate.get('status') != 'accepted' or not original or original.get('source_candidate') != cid:
                raise ValueError('candidate and source identity mismatch')
            canonical = 'lesson_' + cid
            prior = latest.get(canonical)
            source_hash = hashlib.sha256(raw_latest[cid]).hexdigest()
            candidate_hash = hashlib.sha256(candidate_bytes).hexdigest()
            if prior:
                meta = prior.get('identity_migration', {})
                if (meta.get('source_id') != cid or meta.get('source_row_sha256') != source_hash
                        or meta.get('candidate_sha256') != candidate_hash):
                    raise ValueError('canonical identity collision or source changed')
                continue
            source_status = original.get('status')
            if source_status not in {'accepted','provisional','retracted'}:
                raise ValueError('unsupported source status')
            if source_status == 'provisional' and cid not in retired:
                raise ValueError('active provisional identity needs separate review')
            metadata = {'source_id': cid, 'source_row_sha256': source_hash,
                        'candidate_sha256': candidate_hash,
                        'original_identity_fields': {key: original[key] for key in ('id', 'key', 'name') if key in original},
                        'source_status': source_status, 'source_was_superseded': cid in retired}
            if source_status == 'accepted' and cid not in retired:
                row = {**original, 'id': canonical, 'supersedes': cid, 'identity_migration': metadata}
                for key in ('key', 'name'):
                    if row.get(key) == cid:
                        row[key] = canonical
            else:
                row = {'id': canonical, 'source_candidate': cid, 'status': 'retracted',
                       'claim': 'Identity archive for ' + cid + '; consult the original record and its lifecycle for historical guidance.',
                       'reviewer': 'identity-migration', 'rationale': 'Preserve an inactive identity without reviving its historical claim.',
                       'evidence_ids': original.get('evidence_ids', []), 'supersedes': None,
                       'identity_migration': metadata}
            planned.append(row)
        for row in planned:
            _append_lesson_unlocked(stream, row)
    # A prior run may have appended every row but failed to render.
    render_lessons(str(semantic))
    return planned


def main() -> None:
    """Migrate explicit candidate IDs in the repository memory store."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate_ids', nargs='+')
    args = parser.parse_args()
    rows = migrate(args.candidate_ids, BASE / 'memory/semantic', BASE / 'memory/candidates/graduated')
    _LOG.info('appended identity records: %d', len(rows))

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    main()
