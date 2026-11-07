"""Self-tests for the experimental preflight using disposable temporary paths."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('sqlite_lock_preflight.py')


class PreflightTests(unittest.TestCase):
    """Exercise lock recovery, receipt metadata and overwrite refusal."""

    def test_pass_and_refuse_existing_output(self) -> None:
        """A successful run records metadata and refuses reused output paths."""
        with tempfile.TemporaryDirectory() as parent:
            output = Path(parent) / 'new-receipt'
            command = [sys.executable, '-I', str(SCRIPT), '--output', str(output)]
            first = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = output / 'receipt.json'
            original = receipt.read_bytes()
            result = json.loads(original)
            self.assertEqual(result['status'], 'PASS')
            self.assertTrue(result['concurrent_writer_refused_busy'])
            self.assertEqual(result['reopened_values'], ['before', 'after'])
            for key in ('python', 'executable', 'platform', 'machine', 'sqlite_version',
                        'sqlite_source_id', 'sqlite_compile_options'):
                self.assertTrue(result[key], key)
            second = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(receipt.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
