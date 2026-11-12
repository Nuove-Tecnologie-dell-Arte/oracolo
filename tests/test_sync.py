"""Test di backend/sync.py: stampante e diario si sincronizzano in modo
indipendente. Le due sorgenti sono sostituite da funzioni finte."""

import pytest
import requests

from backend import config, db_local, db_online, diario, sync


def _riga(n):
    return {"id": n, "text": f"dal totem {n}", "created_at": None, "status": None, "ip": None, "likes": 0}


def _guasto(*_):
    raise requests.ConnectionError("sorgente spenta")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "REMOTE_API_URL", "https://stampante.test/export.php")


def test_url_stampante_vuoto_sincronizza_solo_il_diario(db, monkeypatch):
    monkeypatch.setattr(config, "REMOTE_API_URL", "")

    def non_chiamare():
        raise AssertionError("con l'URL vuoto la stampante non va interrogata")

    monkeypatch.setattr(db_online, "fetch_all_entries", non_chiamare)
    monkeypatch.setattr(diario, "run_sync_diario", lambda: 5)
    assert sync.run_sync() == 5


def test_stampante_giu_diario_su(db, monkeypatch):
    monkeypatch.setattr(db_online, "fetch_all_entries", _guasto)
    monkeypatch.setattr(diario, "run_sync_diario", lambda: 5)
    assert sync.run_sync() == 5


def test_diario_giu_stampante_su(db, monkeypatch):
    monkeypatch.setattr(db_online, "fetch_all_entries", lambda: [_riga(1), _riga(2)])
    monkeypatch.setattr(diario, "run_sync_diario", _guasto)
    assert sync.run_sync() == 2
    assert len(db_local.get_entries_with_tags("stampante")) == 2


def test_tutto_giu_solleva(db, monkeypatch):
    monkeypatch.setattr(db_online, "fetch_all_entries", _guasto)
    monkeypatch.setattr(diario, "run_sync_diario", _guasto)
    with pytest.raises(requests.ConnectionError):
        sync.run_sync()
