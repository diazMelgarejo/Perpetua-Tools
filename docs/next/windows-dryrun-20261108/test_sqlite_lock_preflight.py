"""Self-tests for the experimental preflight using disposable temporary paths."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from unittest import mock

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

    def test_cleanup_failure_preserves_failure_receipt_and_child_stderr(self) -> None:
        """A failed child and failed cleanup still leave diagnostic evidence."""
        spec = importlib.util.spec_from_file_location('preflight', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class FailedChild:
            """Simulate a holder that reports an error and cannot be killed."""

            stdout = io.StringIO('')
            pid = 12345
            returncode = None

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                """Write the child's diagnostic to the supplied stderr destination."""
                kwargs['stderr'].write('holder diagnostic\n')
                kwargs['stderr'].flush()

            def kill(self) -> None:
                """Inject a cleanup error."""
                raise OSError('kill failed')

            def communicate(self, timeout: int) -> None:
                """Simulate a holder whose exit is observed after kill failed."""
                self.returncode = 1

        class TimedOutChild(FailedChild):
            """Simulate a killed child whose wait does not complete."""

            def kill(self) -> None:
                """Accept the termination request."""

            def communicate(self, timeout: int) -> None:
                """Inject a bounded wait failure."""
                raise subprocess.TimeoutExpired('holder', timeout)

        with tempfile.TemporaryDirectory() as parent:
            module.platform.platform()
            for index, child in enumerate((TimedOutChild, FailedChild)):
                output = Path(parent) / str(index)
                with mock.patch.object(module.subprocess, 'Popen', child):
                    self.assertEqual(module.run(output), 1)
                result = json.loads((output / 'receipt.json').read_text())
                self.assertEqual(result['status'], 'FAIL')
                self.assertEqual(result['holder_pid'], 12345)
                self.assertEqual(result['holder_wait'],
                                 'unconfirmed' if child is TimedOutChild else 'exited')
                self.assertIn('holder_kill', result)
                self.assertIn('holder diagnostic', (output / 'holder.stderr').read_text())

    def test_stderr_close_failure_still_writes_receipt(self) -> None:
        """A diagnostic file close failure cannot suppress a FAIL receipt."""
        spec = importlib.util.spec_from_file_location('preflight_close', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        real_open = Path.open

        class BrokenClose:
            """Wrap a real local file and inject failure when it closes."""

            def __init__(self, file: Any) -> None:
                """Keep the real file available to subprocess creation."""
                self.file = file

            def fileno(self) -> int:
                """Expose the real descriptor to the holder."""
                return self.file.fileno()

            def close(self) -> None:
                """Close the real file before reporting the simulated failure."""
                self.file.close()
                raise OSError('close failed')

        def open_with_close_failure(path: Path, *args: Any, **kwargs: Any) -> Any:
            """Inject failure only for the child's diagnostic file."""
            file = real_open(path, *args, **kwargs)
            return BrokenClose(file) if path.name == 'holder.stderr' else file

        with tempfile.TemporaryDirectory() as parent:
            output = Path(parent) / 'close-failure'
            with mock.patch.object(Path, 'open', open_with_close_failure):
                self.assertEqual(module.run(output), 1)
            result = json.loads((output / 'receipt.json').read_text())
            self.assertEqual(result['status'], 'FAIL')
            self.assertIn('stderr_close_error', result)


if __name__ == '__main__':
    unittest.main()
