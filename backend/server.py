import json
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import requests

from backend import config, db_local, graph, oracle, tagging
from backend.logging_utils import get_logger
from backend.question import generate_questions
from backend.tagdetail import build_tag_detail

log = get_logger(__name__)

UPLOAD_CATEGORIES = ("tesi", "interviste")


def _category_filter(query: dict) -> str | None:
    """Legge ?category=... dalla query string; 'tutti' o assente = nessun filtro."""
    value = (query.get("category") or [""])[0].strip().lower()
    if value in ("", "tutti"):
        return None
    return value


# Soglia usata se il frontend non ne passa una: vedi db_local.get_entries_by_noise_score.
DEFAULT_NOISE_THRESHOLD = 0.5


def _noise_threshold(query: dict) -> float:
    """Legge ?min_score=... dalla query string (0-1); il default se assente
    o non numerico."""
    try:
        value = float((query.get("min_score") or [""])[0])
    except ValueError:
        return DEFAULT_NOISE_THRESHOLD
    return min(1.0, max(0.0, value))

# Momento in cui questo server e' partito: un server legge il codice solo
# all'avvio, quindi dopo un aggiornamento va riavviato.
STARTED_AT = time.strftime("%Y-%m-%d %H:%M:%S")


def _ollama_problem(error: requests.RequestException, host: str | None = None) -> str:
    """Spiega in parole semplici perche' una chiamata a Ollama e' fallita
    (`host`: l'Ollama chiamato, OLLAMA_HOST se non indicato)."""
    if isinstance(error, requests.Timeout):
        return f"Ollama non ha risposto entro {config.OLLAMA_TIMEOUT_SECONDS} secondi"
    if isinstance(error, requests.ConnectionError):
        return f"Ollama non e' raggiungibile su {host or config.OLLAMA_HOST}: e' acceso?"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        detail = error.response.text.strip()[:200]
        return f"Ollama ha risposto con un errore ({error.response.status_code}): {detail}"
    return f"chiamata a Ollama fallita: {error}"


def _health() -> dict:
    """Stato del server e di cio' che serve all'Oracolo, per capire a colpo
    d'occhio cosa non va (GET /api/health)."""
    entries = db_local.get_entries_with_tags()
    status: dict = {
        "avviato": STARTED_AT,
        "entry": len(entries),
        "entry_con_tag": sum(1 for e in entries if e["tags"]),
        "ollama": {"indirizzo": config.OLLAMA_HOST},
    }
    unreachable = status["ollama"]
    try:
        db_local.init_db()
        status["entry_con_vettore"] = len(db_local.get_entry_embeddings())
        status["testi_letti"] = len(db_local.get_sources())
        status["passi_in_biblioteca"] = db_local.get_passages_signature()[0]
        # Un Ollama per la generazione e, se diverso, uno per gli embedding
        # (OLLAMA_EMBED_HOST): ognuno deve avere i suoi modelli.
        if config.OLLAMA_EMBED_HOST == config.OLLAMA_HOST:
            checks = [(status["ollama"], [config.OLLAMA_TAG_MODEL, config.OLLAMA_EMBED_MODEL])]
        else:
            status["ollama_embedding"] = {"indirizzo": config.OLLAMA_EMBED_HOST}
            checks = [
                (status["ollama"], [config.OLLAMA_TAG_MODEL]),
                (status["ollama_embedding"], [config.OLLAMA_EMBED_MODEL]),
            ]
        missing: list[str] = []
        for info, wanted in checks:
            unreachable = info  # se la richiesta fallisce, e' questo l'Ollama irraggiungibile
            response = requests.get(f"{info['indirizzo']}/api/tags", timeout=10)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            absent = [w for w in wanted if not any(m == w or m.startswith(f"{w}:") for m in models)]
            info.update(raggiungibile=True, modelli=models, modelli_mancanti=absent)
            missing += absent
        status["problema"] = (
            f"su Ollama mancano i modelli: {', '.join(missing)}" if missing else None
        )
    except requests.RequestException as error:
        unreachable["raggiungibile"] = False
        status["problema"] = _ollama_problem(error, unreachable["indirizzo"])
    if status.get("problema") is None and not status["entry_con_tag"]:
        status["problema"] = "nessuna entry con tag: esegui 'sync' e 'tag' (o 'seed')"
    return status


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            self._guarded(self._api_get, path)
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        self._guarded(self._api_post, path)

    def _guarded(self, handler, path: str) -> None:
        """Esegue una richiesta API; qualunque errore imprevisto diventa una
        risposta leggibile invece di una connessione chiusa."""
        try:
            handler(path)
        except Exception as error:  # noqa: BLE001 - va segnalato qualunque errore
            log.exception("Errore imprevisto su %s", path)
            self._send_json(
                500, {"error": f"errore interno del server ({type(error).__name__}: {error})"}
            )

    def _api_get(self, path: str) -> None:
        if path == "/api/graph":
            query = parse_qs(urlsplit(self.path).query)
            self._send_json(200, graph.build_graph_json(_category_filter(query)))
            return
        if path.startswith("/api/tag/"):
            tag_name = unquote(path[len("/api/tag/"):])
            query = parse_qs(urlsplit(self.path).query)
            self._handle_tag_detail(tag_name, _category_filter(query))
            return
        if path == "/api/questions":
            self._handle_questions()
            return
        if path == "/api/oracle/question":
            self._handle_oracle_question()
            return
        if path == "/api/oracle/star-question":
            self._handle_star_question()
            return
        if path == "/api/suggestions":
            self._send_json(200, {"questions": oracle.suggestions()})
            return
        if path == "/api/noise":
            query = parse_qs(urlsplit(self.path).query)
            entries = db_local.get_entries_by_noise_score(
                _category_filter(query), _noise_threshold(query)
            )
            self._send_json(200, {"entries": entries})
            return
        if path == "/api/health":
            self._send_json(200, _health())
            return
        self._send_json(404, {"error": "indirizzo sconosciuto"})

    def _api_post(self, path: str) -> None:
        if path == "/api/answer":
            self._handle_answer()
            return
        if path == "/api/ask":
            self._handle_ask()
            return
        if path == "/api/oracle/figure":
            self._handle_figure()
            return
        if path == "/api/upload":
            self._handle_upload()
            return
        self._send_json(404, {"error": "indirizzo sconosciuto"})

    def _handle_tag_detail(self, tag_name: str, category: str | None) -> None:
        detail = build_tag_detail(tag_name, category)
        if detail is None:
            self._send_json(404, {"error": "tag non trovato"})
            return
        self._send_json(200, detail)

    def _handle_questions(self) -> None:
        try:
            questions = generate_questions()
        except requests.RequestException as error:
            self._oracle_unreachable(error)
            return
        if not questions:
            self._send_json(502, {"error": "nessuna domanda disponibile"})
            return
        self._send_json(200, {"questions": questions})

    def _handle_oracle_question(self) -> None:
        """Domanda dell'Oracolo per una stella: ?tag=<nome>&trail=<tappe,precedenti>."""
        query = parse_qs(urlsplit(self.path).query)
        tag = query.get("tag", [""])[0].strip()
        trail = [t for t in query.get("trail", [""])[0].split(",") if t]
        if not tag:
            self._send_json(400, {"error": "manca 'tag'"})
            return
        try:
            question = oracle.question_for_tag(tag, trail)
        except requests.RequestException as error:
            self._oracle_unreachable(error)
            return
        if question is None:
            self._send_json(404, {"error": "tag non trovato"})
            return
        self._send_json(200, {"question": question})

    def _handle_star_question(self) -> None:
        """Domanda che rappresenta una stella: ?tag=<nome>&asked=<domanda che ha
        portato il visitatore dove si trova, facoltativa>. Ogni volta nuova."""
        query = parse_qs(urlsplit(self.path).query)
        tag = query.get("tag", [""])[0].strip()
        asked = query.get("asked", [""])[0].strip() or None
        if not tag:
            self._send_json(400, {"error": "manca 'tag'"})
            return
        try:
            question = oracle.star_question(tag, asked)
        except requests.RequestException as error:
            self._oracle_unreachable(error)
            return
        if question is None:
            self._send_json(404, {"error": "nessuna domanda per questa stella"})
            return
        self._send_json(200, {"question": question})

    def _handle_figure(self) -> None:
        """Figura del viaggio: {"questions": [...], "tags": [...], "exclude": [...],
        "figure": "<gia' scelta, facoltativa>", "speak": <vero per avere la frase>}."""
        body = self._read_json()
        if body is None:
            return
        listed = lambda key: [str(v).strip() for v in body.get(key) or [] if str(v).strip()]
        questions, tags = listed("questions"), listed("tags")
        if not questions:
            self._send_json(400, {"error": "manca 'questions'"})
            return
        try:
            self._send_json(200, oracle.figure(
                questions, tags, listed("exclude"),
                chosen=str(body.get("figure") or "") or None,
                speak=bool(body.get("speak", True)),
            ))
        except requests.RequestException as error:
            self._oracle_unreachable(error)

    def _handle_answer(self) -> None:
        """Testo oracolare: {"question": "<facoltativa>", "tag": "<stella, facoltativa>"}.
        Con la domanda e' la risposta; con la sola stella e' una sentenza sul suo tema."""
        body = self._read_json()
        if body is None:
            return
        question = str(body.get("question") or "").strip() or None
        tag = str(body.get("tag") or "").strip() or None
        if not question and not tag:
            self._send_json(400, {"error": "serve 'question' oppure 'tag'"})
            return
        try:
            self._send_json(200, oracle.answer(question, tag))
        except requests.RequestException as error:
            self._oracle_unreachable(error)

    def _handle_ask(self) -> None:
        """Domanda scritta dal visitatore: lo indirizza a una stella e risponde."""
        body = self._read_json()
        if body is None:
            return
        question = str(body.get("question", "")).strip()
        if not question:
            self._send_json(400, {"error": "manca 'question'"})
            return
        try:
            result = oracle.ask(question)
        except requests.RequestException as error:
            self._oracle_unreachable(error)
            return
        if result is None:
            self._send_json(502, {"error": "la nebulosa e' ancora vuota"})
            return
        self._send_json(200, result)

    def _handle_upload(self) -> None:
        """Carica file .md dal pannello /inserisci.html: {"category": "tesi"|
        "interviste", "files": [{"filename", "text"}, ...]}. Inserisce le
        entry e le tagga subito via Ollama."""
        body = self._read_json()
        if body is None:
            return

        category = str(body.get("category", "")).strip().lower()
        if category not in UPLOAD_CATEGORIES:
            self._send_json(
                400, {"error": f"categoria non valida, deve essere una tra {UPLOAD_CATEGORIES}"}
            )
            return

        files = body.get("files")
        if not isinstance(files, list) or not files:
            self._send_json(400, {"error": "manca 'files' (lista di {filename, text})"})
            return

        texts = [str(f.get("text", "")).strip() for f in files if isinstance(f, dict)]
        texts = [t for t in texts if t]
        if not texts:
            self._send_json(400, {"error": "nessun file con contenuto testuale valido"})
            return

        ids = db_local.insert_local_entries(category, texts)
        log.info("Caricate %d entry in categoria '%s' (id %s)", len(ids), category, ids)

        tagged = tagging.tag_pending_entries()
        self._send_json(200, {"inserted": len(ids), "tagged": tagged})

    def _read_json(self) -> dict | None:
        """Corpo JSON della richiesta; se non e' valido risponde 400 e ritorna None."""
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "body non valido"})
            return None
        return body

    def _oracle_unreachable(self, error: requests.RequestException) -> None:
        log.exception("Chiamata a Ollama fallita (host %s raggiungibile?)", config.OLLAMA_HOST)
        self._send_json(502, {"error": f"L'oracolo non risponde: {_ollama_problem(error)}"})

    def _send_json(self, status: int, payload) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


def run_server() -> None:
    directory = str(Path(config.FRONTEND_DIST_PATH).resolve())
    handler = partial(Handler, directory=directory)
    with ThreadingHTTPServer((config.SERVE_HOST, config.SERVE_PORT), handler) as httpd:
        log.info(
            "Server in ascolto su http://%s:%d (frontend: %s)",
            config.SERVE_HOST, config.SERVE_PORT, directory,
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            log.info("Server fermato")
