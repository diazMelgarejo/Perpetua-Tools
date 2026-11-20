"""Identity migration preserves lifecycle and immutable source history."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / '.agent/tools/migrate_lesson_identity.py'

class IdentityMigrationTests(unittest.TestCase):
    """Preserve prior decisions and source bytes while normalizing identity."""
    def test_collision_refuses_batch_without_appending(self) -> None:
        """Reject an occupied canonical identity before appending any row."""
        spec = importlib.util.spec_from_file_location('migrate_lesson_identity', TOOL)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); semantic = root/'semantic'; semantic.mkdir(); candidates = root/'candidates'; candidates.mkdir()
            rows = [{'id':'aaaaaaaaaaaa','source_candidate':'aaaaaaaaaaaa','status':'accepted'}, {'id':'lesson_aaaaaaaaaaaa','status':'accepted'}]
            path = semantic/'lessons.jsonl'; original = ''.join(json.dumps(x)+'\n' for x in rows).encode(); path.write_bytes(original)
            (candidates/'aaaaaaaaaaaa.json').write_text(json.dumps({'id':'aaaaaaaaaaaa','status':'accepted'}))
            with self.assertRaises(ValueError): module.migrate(['aaaaaaaaaaaa'],semantic,candidates)
            self.assertEqual(path.read_bytes(),original)

    def test_unsuperseded_provisional_source_is_not_reclassified(self) -> None:
        """Require separate review for a still-active provisional identity."""
        spec = importlib.util.spec_from_file_location('migrate_lesson_identity', TOOL)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); semantic = root/'semantic'; semantic.mkdir(); candidates = root/'candidates'; candidates.mkdir()
            path = semantic/'lessons.jsonl'
            original = (json.dumps({'id':'aaaaaaaaaaaa','source_candidate':'aaaaaaaaaaaa','status':'provisional'})+'\n').encode(); path.write_bytes(original)
            (candidates/'aaaaaaaaaaaa.json').write_text(json.dumps({'id':'aaaaaaaaaaaa','status':'accepted'}))
            with self.assertRaises(ValueError): module.migrate(['aaaaaaaaaaaa'],semantic,candidates)
            self.assertEqual(path.read_bytes(),original)

    def test_active_and_retired_keep_lifecycle_and_retry_is_idempotent(self) -> None:
        """Preserve lineage and retirement through partial retries and changed-source refusals."""
        spec = importlib.util.spec_from_file_location('migrate_lesson_identity', TOOL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            semantic = root/'semantic'; semantic.mkdir()
            candidates = root/'candidates'; candidates.mkdir()
            rows = [
                {'id':'aaaaaaaaaaaa','source_candidate':'aaaaaaaaaaaa','status':'accepted','key':'aaaaaaaaaaaa','name':'aaaaaaaaaaaa','supersedes':'lesson_grandparent','claim':'valid historical advice','reviewer':'reviewer','rationale':'reviewed','evidence_ids':['e']},
                {'id':'bbbbbbbbbbbb','source_candidate':'bbbbbbbbbbbb','status':'accepted','claim':'obsolete claim','reviewer':'reviewer','rationale':'reviewed','evidence_ids':['e']},
                {'id':'lesson_replacement','status':'accepted','claim':'corrected claim','supersedes':'bbbbbbbbbbbb'},
            ]
            path = semantic/'lessons.jsonl'
            original = ''.join(json.dumps(x)+'\n' for x in rows).encode(); path.write_bytes(original)
            for cid in ('aaaaaaaaaaaa','bbbbbbbbbbbb'):
                (candidates/f'{cid}.json').write_text(json.dumps({'id':cid,'status':'accepted'}))
            module.migrate(['aaaaaaaaaaaa'],semantic,candidates)
            module.migrate(['aaaaaaaaaaaa','bbbbbbbbbbbb'],semantic,candidates)
            after = path.read_bytes(); self.assertTrue(after.startswith(original))
            additions = [json.loads(x) for x in after[len(original):].splitlines()]
            a,b=additions
            self.assertEqual((a['id'],a['status'],a['supersedes'],a['claim']),('lesson_aaaaaaaaaaaa','accepted','aaaaaaaaaaaa',rows[0]['claim']))
            self.assertEqual((a['key'],a['name']),('lesson_aaaaaaaaaaaa','lesson_aaaaaaaaaaaa'))
            self.assertEqual(a['identity_migration']['original_identity_fields']['key'],'aaaaaaaaaaaa')
            self.assertEqual(rows[0]['supersedes'],'lesson_grandparent')
            self.assertEqual((b['id'],b['status']),('lesson_bbbbbbbbbbbb','retracted'))
            self.assertEqual(b['identity_migration']['source_id'],'bbbbbbbbbbbb')
            self.assertNotEqual(b['claim'], rows[1]['claim'])
            module.migrate(['aaaaaaaaaaaa','bbbbbbbbbbbb'],semantic,candidates)
            self.assertEqual(after,path.read_bytes())
            (candidates/'aaaaaaaaaaaa.json').write_text(json.dumps({'id':'aaaaaaaaaaaa','status':'accepted','changed':True}))
            with self.assertRaises(ValueError): module.migrate(['aaaaaaaaaaaa'],semantic,candidates)
            self.assertEqual(after,path.read_bytes())
            (candidates/'aaaaaaaaaaaa.json').write_text(json.dumps({'id':'aaaaaaaaaaaa','status':'accepted'}))
            changed_source = dict(rows[0], claim='newer correction')
            with path.open('a') as f: f.write(json.dumps(changed_source)+'\n')
            changed = path.read_bytes()
            with self.assertRaises(ValueError): module.migrate(['aaaaaaaaaaaa'],semantic,candidates)
            self.assertEqual(changed,path.read_bytes())

if __name__ == '__main__': unittest.main()
