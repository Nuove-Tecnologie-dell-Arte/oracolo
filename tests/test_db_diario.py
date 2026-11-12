"""Test delle funzioni di backend/db_local.py per il Diario di bordo, su un
DB SQLite temporaneo (niente rete, niente Ollama)."""

import sqlite3

import pytest

from backend import config, db_local
from backend.db_local import DIARIO_ID_BASE


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_DB_PATH", str(tmp_path / "t.db"))
    db_local.init_db()


def _pensiero(n: int, text: str = "ciao", gruppo: str = "4° anno") -> dict:
    return {"id": DIARIO_ID_BASE + n, "text": text, "created_at": "2026-11-12", "gruppo": gruppo}


def _riga(entry_id: int) -> sqlite3.Row | None:
    with db_local.get_connection() as conn:
        return conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()


def test_upsert_scrive_categoria_e_gruppo(db):
    assert db_local.upsert_diario_entries([_pensiero(7)]) == 1
    (entry,) = db_local.get_entries_with_tags("diario")
    assert entry["id"] == DIARIO_ID_BASE + 7
    assert entry["group"] == "4° anno"
    assert entry["source"] is None
    row = _riga(DIARIO_ID_BASE + 7)
    assert row["category"] == "diario" and row["likes"] == 0 and row["created_at"] == "2026-11-12"


def test_testo_cambiato_azzera_tagged_at(db):
    db_local.upsert_diario_entries([_pensiero(1, "prima")])
    with db_local.get_connection() as conn:
        conn.execute("UPDATE entries SET tagged_at = '2026-11-12' WHERE id = ?", (DIARIO_ID_BASE + 1,))

    db_local.upsert_diario_entries([_pensiero(1, "prima")])
    assert _riga(DIARIO_ID_BASE + 1)["tagged_at"] == "2026-11-12"

    db_local.upsert_diario_entries([_pensiero(1, "dopo")])
    assert _riga(DIARIO_ID_BASE + 1)["tagged_at"] is None


def test_pulizia_tocca_solo_il_diario(db):
    db_local.upsert_diario_entries([_pensiero(1), _pensiero(2)])
    db_local.upsert_entries(
        [{"id": 5, "text": "dal totem", "created_at": None, "status": None, "ip": None, "likes": 0}]
    )
    assert db_local.delete_diario_entries_except({DIARIO_ID_BASE + 1}) == 1
    assert _riga(DIARIO_ID_BASE + 1) is not None
    assert _riga(DIARIO_ID_BASE + 2) is None
    assert _riga(5) is not None


def test_init_db_aggiunge_gruppo_a_db_vecchio(tmp_path, monkeypatch):
    path = tmp_path / "vecchio.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE entries (id INTEGER PRIMARY KEY, text TEXT NOT NULL, created_at TEXT, "
                 "status TEXT, ip TEXT, likes INTEGER, synced_at TEXT, tagged_at TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(config, "LOCAL_DB_PATH", str(path))

    db_local.init_db()

    with db_local.get_connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(entries)")}
    assert "gruppo" in columns


def test_altre_categorie_hanno_group_none(db):
    db_local.upsert_entries(
        [{"id": 5, "text": "dal totem", "created_at": None, "status": None, "ip": None, "likes": 0}]
    )
    (entry,) = db_local.get_entries_with_tags("stampante")
    assert entry["group"] is None
