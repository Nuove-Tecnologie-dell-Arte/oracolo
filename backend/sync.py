from backend import config, db_local, db_online, diario
from backend.logging_utils import get_logger

log = get_logger(__name__)


def _sync_stampante() -> int:
    rows = db_online.fetch_all_entries()
    n = db_local.upsert_entries(rows)
    log.info("Stampante: %d entry sincronizzate", n)
    return n


def run_sync() -> int:
    """Scarica i pensieri da tutte le provenienze remote (stampante dal MySQL
    online, Diario di bordo dalla sua API) e li sincronizza in locale.

    Le provenienze sono indipendenti: se una non risponde l'errore finisce
    nel log e l'altra si scarica comunque. Solleva l'errore solo se tutte
    quelle attive falliscono. Ritorna il numero di entry sincronizzate.
    """
    log.info("Inizializzo il DB locale (%s)...", config.LOCAL_DB_PATH)
    db_local.init_db()

    sources = [("diario", diario.run_sync_diario)]
    if config.REMOTE_API_URL:
        sources.insert(0, ("stampante", _sync_stampante))
    else:
        log.info("Stampante saltata: REMOTE_API_URL vuoto in .env")

    total, last_error, failures = 0, None, 0
    for name, sync_source in sources:
        try:
            total += sync_source()
        except Exception as error:  # una provenienza giu' non ferma le altre
            log.exception("Sync di '%s' fallito: proseguo con le altre provenienze", name)
            last_error, failures = error, failures + 1
    if failures == len(sources) and last_error is not None:
        raise last_error
    return total
