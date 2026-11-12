"""Il gruppo dei pensieri del diario arriva al sito accanto a `source`: nel
dettaglio di una stella (backend/tagdetail.py) e nei pensieri citati
dall'Oracolo (backend/oracle.py)."""

import pytest

from backend import config, db_local, oracle
from backend.db_local import DIARIO_ID_BASE
from backend.tagdetail import build_tag_detail

DIARIO = DIARIO_ID_BASE + 1


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_DB_PATH", str(tmp_path / "t.db"))
    db_local.init_db()
    db_local.upsert_diario_entries(
        [{"id": DIARIO, "text": "il mare del lab", "created_at": "2026-11-12", "gruppo": "4° anno"}]
    )
    db_local.upsert_entries(
        [{"id": 5, "text": "il mare dal totem", "created_at": None, "status": None, "ip": None, "likes": 0}]
    )
    for entry_id in (DIARIO, 5):
        db_local.set_entry_tags(entry_id, ["mare", "casa"])


def test_dettaglio_della_stella_porta_il_gruppo(db):
    detail = build_tag_detail("mare")
    groups = {e["id"]: e["group"] for e in detail["entries"]}
    assert groups == {DIARIO: "4° anno", 5: None}
    related = {e["id"]: e["group"] for e in detail["related"][0]["entries"]}
    assert related[DIARIO] == "4° anno"


def test_filtro_diario(db):
    assert build_tag_detail("mare", "diario")["count"] == 1


def test_pensiero_dell_oracolo_porta_il_gruppo():
    assert oracle._view({"id": 1, "text": "t", "group": "Docenti"})["group"] == "Docenti"
    assert oracle._view({"id": 2, "text": "t"})["group"] is None
