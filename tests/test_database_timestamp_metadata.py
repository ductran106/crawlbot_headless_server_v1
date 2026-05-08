from pathlib import Path

from src.storage.database import DatabaseManager


def test_database_saves_exact_timestamp_metadata(tmp_path: Path):
    db = DatabaseManager(str(tmp_path / "messages.db"))
    db.save_messages([
        {
            "raw_message": "*[18/03/2026 18:54:39] Alice: Xin chào",
            "content": "Xin chào",
            "sender": "Alice",
            "sent_at_exact": "2026-03-18 18:54:39",
            "sent_at_ms": 1773834879000,
            "ingested_at": "2026-03-18 18:55:01",
            "timestamp_source": "exact_from_qid",
        }
    ], "RETURN ROOM LỊCH")

    import sqlite3
    conn = sqlite3.connect(str(tmp_path / "messages.db"))
    cur = conn.cursor()
    cur.execute("select timestamp, sender, content, sent_at_exact, sent_at_ms, ingested_at, timestamp_source from messages limit 1")
    timestamp, sender, content, sent_at_exact, sent_at_ms, ingested_at, timestamp_source = cur.fetchone()
    conn.close()

    assert timestamp == "18/03/2026 18:54:39"
    assert sender == "Alice"
    assert content == "Xin chào"
    conn.close()

    assert sent_at_exact == "2026-03-18 18:54:39"
    assert sent_at_ms == 1773834879000
    assert ingested_at == "2026-03-18 18:55:01"
    assert timestamp_source == "exact_from_qid"
