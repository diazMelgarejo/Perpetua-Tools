"""Archive stale working context. Tasks don't span nights by default."""
import os, datetime, shutil

STALE_DAYS = 2


def archive_stale_workspace(working_dir, archive_dir):
    workspace = os.path.join(working_dir, "WORKSPACE.md")
    if not os.path.exists(workspace):
        return False
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(workspace))
    if (datetime.datetime.now() - mtime).days < STALE_DAYS:
        return False
    os.makedirs(archive_dir, exist_ok=True)
    dest = os.path.join(archive_dir,
                        f"workspace_{datetime.date.today().isoformat()}.md")
    shutil.move(workspace, dest)
    return True
