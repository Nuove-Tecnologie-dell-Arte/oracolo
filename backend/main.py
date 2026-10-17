import argparse
import time
from pathlib import Path

import schedule

from backend import config, db_local, embeddings, library, seed, server, sync, tagging
from backend.export_static import export_static
from backend.logging_utils import get_logger, setup_logging

log = get_logger(__name__)


def do_sync() -> None:
    n = sync.run_sync()
    print(f"[sync] {n} entry sincronizzate dalla sorgente remota")


def do_tag(args: argparse.Namespace) -> None:
    if args.retag:
        reset = db_local.reset_all_tagged()
        print(f"[tag] --retag: {reset} entry gia' taggate verranno riprocessate da capo")
    n = tagging.tag_pending_entries()
    print(f"[tag] {n} entry taggate con Ollama")


def do_embed() -> None:
    entries = db_local.get_tagged_entries()
    n = embeddings.ensure_entry_embeddings(entries)
    print(f"[embed] {n} entry preparate per l'Oracolo (vettori di similarita')")


def do_ingest(args: argparse.Namespace) -> None:
    db_local.init_db()
    if args.forget:
        removed = db_local.delete_source(args.forget)
        print(f"[ingest] '{args.forget}': " + ("rimosso dalla nebulosa" if removed else "non era tra i testi letti"))
        return
    if not args.list:
        for result in library.ingest_all(args.stars):
            if "skipped" in result:
                print(f"[ingest] {result['file']}: saltato ({result['skipped']})")
            else:
                print(
                    f"[ingest] {result['file']}: {result['passages']} passi in biblioteca, "
                    f"{result['fragments']} citazioni nella nebulosa"
                )
    sources = db_local.get_sources()
    print(f"[ingest] testi letti dall'Oracolo: {len(sources)}")
    for source in sources:
        print(
            f"  - {source['author']}, {source['title']} "
            f"({source['passages']} passi, {source['fragments']} citazioni) [{source['file']}]"
        )


def do_serve() -> None:
    server.run_server()


def do_seed() -> None:
    seed.seed_test_data()
    print("[seed] dati di prova inseriti nel DB locale")


def do_export(args: argparse.Namespace) -> None:
    export_static(Path(args.out), args.base)
    print(f"[export] export statico pronto in {args.out} (base: {args.base})")


def do_pipeline(args: argparse.Namespace) -> None:
    do_sync()
    do_tag(args)
    do_embed()


def run_loop(args: argparse.Namespace) -> None:
    print(
        f"[run] avvio con intervallo di {config.SYNC_INTERVAL_MINUTES} minuti "
        "(Ctrl+C per fermare)"
    )
    do_pipeline(args)
    # --retag si applica solo al primo giro: ai successivi (automatici, ogni
    # SYNC_INTERVAL_MINUTES) non va ripetuto, altrimenti si rifarebbe tutto
    # il tagging per sempre invece che solo le entry nuove.
    recurring_args = argparse.Namespace(**{**vars(args), "retag": False})
    schedule.every(config.SYNC_INTERVAL_MINUTES).minutes.do(do_pipeline, recurring_args)
    while True:
        schedule.run_pending()
        time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracolo: sync + tagging + grafo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sync", help="Sincronizza le entry da MySQL a locale")
    tag_parser = subparsers.add_parser("tag", help="Tagga le entry non ancora processate")
    tag_parser.add_argument(
        "--retag", action="store_true",
        help="Riprocessa anche le entry gia' taggate (es. per ricalcolare 'rumore' dopo un aggiornamento)",
    )
    subparsers.add_parser(
        "embed",
        help="Prepara le entry per l'Oracolo (vettori di similarita'); altrimenti avviene alla prima domanda",
    )
    ingest_parser = subparsers.add_parser(
        "ingest",
        help=f"Fa leggere all'Oracolo i PDF e i TXT nella cartella '{config.TEXTS_DIR}/'",
    )
    ingest_parser.add_argument(
        "--stars", type=int, default=None,
        help=f"Citazioni di ogni testo che entrano nella nebulosa (default: {config.LIBRARY_STARS_PER_SOURCE})",
    )
    ingest_parser.add_argument("--forget", metavar="FILE", help="Toglie dalla nebulosa un testo gia' letto")
    ingest_parser.add_argument("--list", action="store_true", help="Elenca i testi letti, senza leggerne di nuovi")
    pipeline_parser = subparsers.add_parser("pipeline", help="Esegue sync + tag + embed una volta")
    pipeline_parser.add_argument("--retag", action="store_true", help="Vedi 'tag --retag'")
    run_parser = subparsers.add_parser("run", help="Esegue la pipeline in loop, a intervalli")
    run_parser.add_argument("--retag", action="store_true", help="Vedi 'tag --retag' (si applica solo al primo giro)")
    subparsers.add_parser(
        "serve",
        help="Avvia il webserver locale che serve il frontend Nebulosa e /api/graph, /api/tag/<nome>",
    )
    subparsers.add_parser(
        "seed", help="Inserisce dati di prova gia' taggati (per testare il grafo)"
    )
    export_parser = subparsers.add_parser(
        "export",
        help="Esporta una fotografia statica (HTML + JSON) della Nebulosa, per hosting solo PHP/HTML",
    )
    export_parser.add_argument(
        "--out", default="export/nebulosa", help="Cartella di output (default: export/nebulosa)"
    )
    export_parser.add_argument(
        "--base",
        default="/mondoarotoli/nebulosa/",
        help="Percorso in cui verra' caricata su hosting (default: /mondoarotoli/nebulosa/)",
    )

    args = parser.parse_args()
    setup_logging()
    log.info("DB locale: %s", Path(config.LOCAL_DB_PATH).resolve())
    # Crea lo schema o applica le migrazioni (es. nuove colonne) qualunque
    # sia il comando: altrimenti un DB esistente creato da una versione
    # precedente resta senza le colonne nuove finche' non si esegue 'sync'
    # o 'ingest' (gli unici che chiamavano init_db() per conto loro).
    db_local.init_db()

    commands = {
        "sync": do_sync,
        "tag": lambda: do_tag(args),
        "embed": do_embed,
        "ingest": lambda: do_ingest(args),
        "pipeline": lambda: do_pipeline(args),
        "run": lambda: run_loop(args),
        "serve": do_serve,
        "seed": do_seed,
        "export": lambda: do_export(args),
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
