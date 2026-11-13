"""Il Diario di bordo (https://diario.nuovetecnologiedellarte.it/) come
provenienza dei pensieri della nebulosa, accanto alla stampante.

Il diario ha un'API pubblica in JSON, senza chiave:
- GET /api/categorie -> {"categorie": [{"chiave", "nome", "conteggio"}], ...}
- GET /api/pensieri?pagina=N&per_pagina=M -> {"totale", "pagina", "pagine",
  "pensieri": [{"id", "testo", "categoria", "giorno"}]}

I pensieri entrano nel DB locale con categoria 'diario', id nella fascia
DIARIO_ID_BASE e il nome leggibile del gruppo di chi scrive. Quelli che sul
diario non ci sono piu' vengono tolti, ma solo dopo uno scaricamento completo.
"""

import requests

from backend import config, db_local
from backend.db_local import DIARIO_ID_BASE
from backend.logging_utils import get_logger

log = get_logger(__name__)

# Pensieri per pagina chiesti al diario.
PER_PAGINA = 100


def _get(session, path: str, params: dict | None = None) -> dict:
    response = session.get(
        f"{config.DIARIO_API_URL}{path}",
        params=params,
        timeout=config.REMOTE_API_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def fetch_pensieri(session=requests) -> tuple[list[dict], dict[str, str]]:
    """Scarica tutti i pensieri del diario (tutte le pagine) e i nomi dei
    gruppi ({chiave: nome}). Qualunque errore solleva un'eccezione: un
    elenco a meta' non deve mai arrivare alla pulizia."""
    nomi = {c["chiave"]: c["nome"] for c in _get(session, "/api/categorie")["categorie"]}
    pensieri: list[dict] = []
    pagina, pagine, totale = 1, 1, None
    while pagina <= pagine:
        dati = _get(session, "/api/pensieri", {"pagina": pagina, "per_pagina": PER_PAGINA})
        pensieri.extend(dati["pensieri"])
        pagine = dati["pagine"]
        if totale is None:
            totale = dati["totale"]
        pagina += 1
    # Un elenco che non torna con il totale dichiarato (pensiero cancellato
    # mentre si leggevano le pagine, risposta vuota per errore) e' a meta':
    # meglio rinunciare e riprovare al prossimo sync che cancellare per sbaglio.
    if len(pensieri) != totale:
        raise ValueError(f"il diario dichiara {totale} pensieri ma ne sono arrivati {len(pensieri)}")
    return pensieri, nomi


def to_entries(pensieri: list[dict], nomi: dict[str, str]) -> list[dict]:
    """Pensieri del diario nel formato di db_local.upsert_diario_entries. I
    testi vuoti vengono scartati; un gruppo sconosciuto resta con la sua chiave."""
    entries = []
    for p in pensieri:
        text = (p.get("testo") or "").strip()
        if not text:
            continue
        entries.append({
            "id": DIARIO_ID_BASE + p["id"],
            "text": text,
            "created_at": p.get("giorno"),
            "gruppo": nomi.get(p["categoria"], p["categoria"]),
        })
    return entries


def run_sync_diario() -> int:
    """Porta i pensieri del diario nel DB locale e toglie quelli spariti.
    Ritorna quante entry ha scritto (0 se il diario e' disattivato)."""
    if not config.DIARIO_API_URL:
        log.info("Diario di bordo disattivato (DIARIO_API_URL vuoto)")
        return 0
    log.info("Richiesta al Diario di bordo (%s)...", config.DIARIO_API_URL)
    pensieri, nomi = fetch_pensieri()
    entries = to_entries(pensieri, nomi)
    n = db_local.upsert_diario_entries(entries)
    removed = db_local.delete_diario_entries_except({e["id"] for e in entries})
    log.info("Diario: %d pensieri sincronizzati, %d tolti perche' non piu' sul diario", n, removed)
    return n
