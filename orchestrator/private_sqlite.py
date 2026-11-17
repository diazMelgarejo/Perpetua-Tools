"""Private, user-owned SQLite state shared by PT's durable runtime stores.

One opener for every store that must be safe to share across processes (the dispatch claim ledger and
the spend ledger). It refuses symlinks, directories or files owned by another user or writable by
others, and files with extra hard links. POSIX mode bits make no claim about native Windows ACLs:
Windows delegates to PT's existing allow-only ACL helper, whose behavior is not qualified here.
SQLite reopens a pathname after descriptor validation, so trusted ancestors and same-user processes
remain an operational assumption; this is not a handle-relative filesystem sandbox.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def open_private_sqlite(
    state_dir: Path | str,
    filename: str,
    *,
    dir_label: str,
    file_label: str,
    timeout: float = 2,
) -> sqlite3.Connection:
    """Open ``state_dir/filename`` as a private SQLite database, creating it on first use.

    ``dir_label`` and ``file_label`` name the store in refusal messages (for example "dispatch state"
    and "dispatch ledger"). Raises PermissionError for any unsafe directory, ancestor or file. The
    connection uses ``synchronous=FULL`` and the caller owns its transactions and closing.
    """
    from stat import S_ISDIR, S_ISLNK, S_ISREG, S_ISVTX

    state_dir = Path(state_dir)
    if state_dir.is_symlink():
        raise PermissionError(f"{dir_label} directory cannot be a symlink")
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        ancestors = list(state_dir.absolute().parents)
        visited: set[Path] = set()
        link_count = 0
        while ancestors:
            ancestor = ancestors.pop()
            if ancestor in visited:
                continue
            visited.add(ancestor)
            info = ancestor.lstat()
            if S_ISLNK(info.st_mode):
                if info.st_uid not in {0, os.getuid()}:
                    raise PermissionError(f"{dir_label} ancestor symlink must be trusted")
                link_count += 1
                if link_count > 40:
                    raise PermissionError(f"{dir_label} ancestor symlink chain is too long")
                target = Path(os.readlink(ancestor))
                if ".." in target.parts:
                    raise PermissionError(f"{dir_label} ancestor symlink target is not attestable")
                if not target.is_absolute():
                    target = ancestor.parent / target
                ancestors.append(target)
                ancestors.extend(target.parents)
                continue
            # Root-owned sticky temporary directories protect user-owned
            # descendants from renaming by other unprivileged users.
            sticky_root = info.st_uid == 0 and bool(info.st_mode & S_ISVTX)
            if not S_ISDIR(info.st_mode) or info.st_uid not in {0, os.getuid()} or (info.st_mode & 0o022 and not sticky_root):
                raise PermissionError(f"{dir_label} ancestor must be a trusted directory")
    directory_info = state_dir.lstat()
    if not S_ISDIR(directory_info.st_mode):
        raise PermissionError(f"{dir_label} directory must be a real directory")
    if os.name != "nt" and (directory_info.st_uid != os.getuid() or directory_info.st_mode & 0o022):
        raise PermissionError(f"{dir_label} directory must be user-owned and not writable by others")
    if os.name == "nt":
        from .alphaclaw_tls_proxy import _secure_path

        _secure_path(state_dir, is_directory=True)
    path = state_dir / filename
    if path.is_symlink():
        raise PermissionError(f"{file_label} cannot be a symlink")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(fd)
        named = path.lstat()
        if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
            raise PermissionError(f"{file_label} changed while opening")
        if not S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PermissionError(f"{file_label} must be a private regular file")
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise PermissionError(f"{file_label} permissions must be private")
    finally:
        os.close(fd)
    if os.name == "nt":
        _secure_path(path)
    connection = sqlite3.connect(path, timeout=timeout)
    connection.execute("PRAGMA synchronous=FULL")
    return connection
