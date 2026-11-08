"""Experimental disposable SQLite WAL and process-lock preflight; not qualification."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time


def hold(db_path: str) -> None:
    """Hold a write transaction until the parent terminates this process."""
    with closing(sqlite3.connect(db_path, timeout=1)) as db:
        db.execute('BEGIN IMMEDIATE')
        print('LOCKED', flush=True)
        time.sleep(60)


def stop_holder(process: subprocess.Popen, result: dict) -> bool:
    """Request termination and independently wait; record an unconfirmed exit."""
    result['holder_pid'] = process.pid
    try:
        process.kill()
        result['holder_kill'] = 'requested'
    except Exception as exc:
        result['holder_kill'] = f'{type(exc).__name__}: {exc}'
    try:
        process.communicate(timeout=10)
        result['holder_wait'] = 'exited'
        result['holder_death_exit_code'] = process.returncode
    except Exception as exc:
        result['holder_wait'] = 'unconfirmed'
        result['holder_wait_error'] = f'{type(exc).__name__}: {exc}'
    return result['holder_kill'] == 'requested' and result['holder_wait'] == 'exited'


def run(output: Path) -> int:
    """Run the disposable experiment and exclusively create a local receipt."""
    output.mkdir(mode=0o700)  # exclusive: never reuse an existing directory
    db_path = output / 'preflight.sqlite3'
    result = {'status': 'FAIL', 'python': sys.version, 'executable': sys.executable,
              'platform': platform.platform(), 'machine': platform.machine(),
              'sqlite_version': sqlite3.sqlite_version}
    process = None
    child_stderr = None
    try:
        with closing(sqlite3.connect(db_path)) as db, db:
            result['sqlite_source_id'] = db.execute('SELECT sqlite_source_id()').fetchone()[0]
            result['sqlite_compile_options'] = [row[0] for row in db.execute('PRAGMA compile_options')]
            result['journal_mode'] = db.execute('PRAGMA journal_mode=WAL').fetchone()[0]
            if result['journal_mode'].lower() != 'wal':
                raise RuntimeError('WAL unavailable')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE checks (value TEXT NOT NULL)')
            db.execute("INSERT INTO checks VALUES ('before')")
        child_stderr = (output / 'holder.stderr').open('x', encoding='utf-8')
        process = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--holder', str(db_path)],
                                   stdout=subprocess.PIPE, stderr=child_stderr, text=True)
        # Bounded wait: child prints only after the exclusive writer lock is acquired.
        # Poll a small signal file-free handshake with a timeout via a daemon reader.
        import queue
        import threading
        messages = queue.Queue()
        threading.Thread(target=lambda: messages.put(process.stdout.readline()), daemon=True).start()
        try:
            ready = messages.get(timeout=10)
        except queue.Empty as exc:
            raise RuntimeError('holder readiness timeout') from exc
        if ready.strip() != 'LOCKED':
            raise RuntimeError('holder did not acquire lock')
        try:
            with closing(sqlite3.connect(db_path, timeout=0.2)) as contender, contender:
                contender.execute('BEGIN IMMEDIATE')
        except sqlite3.OperationalError as exc:
            if getattr(exc, 'sqlite_errorcode', None) != sqlite3.SQLITE_BUSY:
                raise
            result['concurrent_writer_refused_busy'] = True
        else:
            raise RuntimeError('concurrent writer unexpectedly acquired lock')
        stopped = stop_holder(process, result)
        process = None
        if not stopped:
            raise RuntimeError('holder termination or wait failed')
        with closing(sqlite3.connect(db_path, timeout=5)) as reopened, reopened:
            reopened.execute('PRAGMA synchronous=FULL')
            reopened.execute('BEGIN IMMEDIATE')
            reopened.execute("INSERT INTO checks VALUES ('after')")
            reopened.commit()
        with closing(sqlite3.connect(db_path)) as reopened:
            result['reopened_values'] = [row[0] for row in reopened.execute('SELECT value FROM checks ORDER BY rowid')]
            result['integrity_check'] = reopened.execute('PRAGMA integrity_check').fetchone()[0]
            result['reopened_journal_mode'] = reopened.execute('PRAGMA journal_mode').fetchone()[0]
        if result['reopened_values'] != ['before', 'after'] or result['integrity_check'] != 'ok' or result['reopened_journal_mode'].lower() != 'wal':
            raise RuntimeError('reopen or integrity check failed')
        result['status'] = 'PASS'
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['error'] = str(exc)
    finally:
        if process is not None:
            if not stop_holder(process, result):
                result['status'] = 'FAIL'
        if child_stderr is not None:
            try:
                child_stderr.close()
            except Exception as exc:
                result['status'] = 'FAIL'
                result['stderr_close_error'] = f'{type(exc).__name__}: {exc}'
        with (output / 'receipt.json').open('x', encoding='utf-8') as receipt:
            json.dump(result, receipt, indent=2)
            receipt.write('\n')
    print(result['status'])
    return 0 if result['status'] == 'PASS' else 1


def main() -> int:
    """Parse the public invocation or start the internal holder process."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new directory under an existing approved local parent')
    parser.add_argument('--holder', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.holder:
        hold(args.holder)
        return 0
    if not args.output:
        parser.error('--output is required')
    return run(args.output)


if __name__ == '__main__':
    sys.exit(main())
