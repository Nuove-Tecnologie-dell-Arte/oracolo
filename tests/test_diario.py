"""Test di backend/diario.py senza rete: le risposte del diario arrivano da
una sessione HTTP finta, il DB e' un SQLite temporaneo."""

import pytest
import requests

from backend import config, db_local, diario
from backend.db_local import DIARIO_ID_BASE
from backend.diario import fetch_pensieri, run_sync_diario, to_entries

BASE = "https://diario.test"


class _Risposta:
    def __init__(self, dati=None, errore: bool = False):
        self._dati = dati
        self._errore = errore

    def raise_for_status(self):
        if self._errore:
            raise requests.HTTPError("500")

    def json(self):
        return self._dati


class _Sessione:
    """Risponde per percorso e pagina; registra le chiamate fatte."""

    def __init__(self, categorie, pagine, errore_a_pagina=None, totale=None):
        self.categorie = categorie
        self.pagine = pagine
        self.errore_a_pagina = errore_a_pagina
        # quanti pensieri il diario dichiara (di norma: quelli che manda)
        self.totale = sum(map(len, pagine)) if totale is None else totale
        self.chiamate = []

    def get(self, url, params=None, timeout=None):
        self.chiamate.append((url, params))
        if url == f"{BASE}/api/categorie":
            return _Risposta({"categorie": self.categorie, "testo_max": 5000})
        assert url == f"{BASE}/api/pensieri"
        n = params["pagina"]
        if n == self.errore_a_pagina:
            return _Risposta(errore=True)
        return _Risposta({"totale": self.totale, "pagina": n,
                          "pagine": len(self.pagine), "pensieri": self.pagine[n - 1]})


CATEGORIE = [{"chiave": "anno-4", "nome": "4° anno", "conteggio": 1},
             {"chiave": "docenti", "nome": "Docenti", "conteggio": 1}]


def _p(n, testo="un pensiero", categoria="anno-4"):
    return {"id": n, "testo": testo, "categoria": categoria, "giorno": "2026-11-12"}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCAL_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "DIARIO_API_URL", BASE)
    db_local.init_db()


def _ids_diario():
    return {e["id"] for e in db_local.get_entries_with_tags("diario")}


def test_to_entries():
    out = to_entries(
        [{"id": 3, "testo": " ciao ", "categoria": "anno-4", "giorno": "2026-11-12"},
         {"id": 4, "testo": "  ", "categoria": "docenti", "giorno": "2026-11-12"},
         {"id": 5, "testo": "x", "categoria": "nuovo", "giorno": None}],
        {"anno-4": "4° anno"},
    )
    assert out == [
        {"id": DIARIO_ID_BASE + 3, "text": "ciao", "created_at": "2026-11-12", "gruppo": "4° anno"},
        {"id": DIARIO_ID_BASE + 5, "text": "x", "created_at": None, "gruppo": "nuovo"},
    ]


def test_fetch_legge_tutte_le_pagine(monkeypatch):
    monkeypatch.setattr(config, "DIARIO_API_URL", BASE)
    sessione = _Sessione(CATEGORIE, [[_p(3), _p(2)], [_p(1, categoria="docenti")]])
    pensieri, nomi = fetch_pensieri(sessione)
    assert [p["id"] for p in pensieri] == [3, 2, 1]
    assert nomi == {"anno-4": "4° anno", "docenti": "Docenti"}
    assert [c[1]["pagina"] for c in sessione.chiamate if c[1]] == [1, 2]


def test_fetch_errore_a_meta_solleva(monkeypatch):
    monkeypatch.setattr(config, "DIARIO_API_URL", BASE)
    sessione = _Sessione(CATEGORIE, [[_p(2)], [_p(1)]], errore_a_pagina=2)
    with pytest.raises(requests.HTTPError):
        fetch_pensieri(sessione)


def test_fetch_elenco_incompleto_solleva(monkeypatch):
    # Il diario dichiara 3 pensieri ma ne arrivano 2 (un pensiero cancellato
    # mentre si leggevano le pagine, o una risposta vuota per errore): senza
    # l'elenco intero la pulizia toglierebbe pensieri ancora validi.
    monkeypatch.setattr(config, "DIARIO_API_URL", BASE)
    sessione = _Sessione(CATEGORIE, [[_p(3)], [_p(1)]], totale=3)
    with pytest.raises(ValueError):
        fetch_pensieri(sessione)


def test_fetch_risposta_vuota_ma_con_pensieri_dichiarati_solleva(monkeypatch):
    monkeypatch.setattr(config, "DIARIO_API_URL", BASE)
    sessione = _Sessione(CATEGORIE, [[]], totale=36)
    with pytest.raises(ValueError):
        fetch_pensieri(sessione)


def test_sync_scrive_e_pulisce(db, monkeypatch):
    db_local.upsert_diario_entries(
        [{"id": DIARIO_ID_BASE + 9, "text": "cancellato", "created_at": None, "gruppo": "Docenti"}]
    )
    monkeypatch.setattr(diario, "fetch_pensieri", lambda: ([_p(1), _p(2)], {"anno-4": "4° anno"}))
    assert run_sync_diario() == 2
    assert _ids_diario() == {DIARIO_ID_BASE + 1, DIARIO_ID_BASE + 2}


def test_sync_errore_non_scrive_ne_pulisce(db, monkeypatch):
    db_local.upsert_diario_entries(
        [{"id": DIARIO_ID_BASE + 9, "text": "resta", "created_at": None, "gruppo": "Docenti"}]
    )

    def guasto():
        raise requests.ConnectionError("diario spento")

    monkeypatch.setattr(diario, "fetch_pensieri", guasto)
    with pytest.raises(requests.ConnectionError):
        run_sync_diario()
    assert _ids_diario() == {DIARIO_ID_BASE + 9}


def test_sync_totale_zero_svuota_il_diario(db, monkeypatch):
    db_local.upsert_diario_entries(
        [{"id": DIARIO_ID_BASE + 9, "text": "via", "created_at": None, "gruppo": "Docenti"}]
    )
    db_local.upsert_entries(
        [{"id": 5, "text": "dal totem", "created_at": None, "status": None, "ip": None, "likes": 0}]
    )
    monkeypatch.setattr(diario, "fetch_pensieri", lambda: ([], {}))
    assert run_sync_diario() == 0
    assert _ids_diario() == set()
    assert len(db_local.get_entries_with_tags("stampante")) == 1


def test_sync_disattivato_con_url_vuoto(db, monkeypatch):
    monkeypatch.setattr(config, "DIARIO_API_URL", "")

    def non_chiamare():
        raise AssertionError("con l'URL vuoto il diario non va interrogato")

    monkeypatch.setattr(diario, "fetch_pensieri", non_chiamare)
    assert run_sync_diario() == 0
