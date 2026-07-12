from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lessons_lan_examples_keep_role_and_stale_address_semantics():
    text = (ROOT / "docs" / "LESSONS.md").read_text(encoding="utf-8")
    heading = "## 2026-06-28 — LAN peer bidirectional talk attempts (Win session) | Cursor"
    start = text.index(heading)
    end = text.index("\n---\n", start)
    section = text[start:end]

    assert "<YOUR_LAN_IP>" not in section
    assert "`.110`" not in section
    assert "`.102`" not in section
    assert "<WIN_LAN_IP>" in section
    assert "<MAC_LAN_IP>" in section
    assert "<OLD_WIN_LAN_IP>" in section
