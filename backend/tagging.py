import json
from functools import lru_cache
from pathlib import Path

import requests

from backend import config, db_local, ollama
from backend.logging_utils import get_logger
from backend.progress import advance, new_bar

log = get_logger(__name__)

# Tag assegnato alle entry da cui Ollama non riesce a estrarre nessun tag
# (testo spazzatura, troppo corto o senza senso): senza, l'entry resterebbe
# "non taggata" per sempre e verrebbe ritentata a ogni tagging successivo.
NOISE_TAG = "rumore di fondo"

TAG_PROMPT = """Analizza il seguente testo e assegna da 1 a {max_tags} tag \
brevi (una o due parole ciascuno) che ne descrivano il tema/argomento principale.

Valuta anche quanto il testo sia "rumore di fondo": scritto a caso, una prova \
di scrittura, spazzatura o incomprensibile, senza un pensiero vero (un pensiero \
breve ma sensato NON e' rumore di fondo, anche se generico).

Rispondi SOLO con un oggetto JSON con questa forma esatta, senza altro testo:
{{"tags": ["amore", "gioco"], "rumore": 0.0}}

"rumore" e' un numero da 0 (sicuramente un pensiero vero) a 1 (sicuramente \
rumore di fondo).

Testo:
\"\"\"{text}\"\"\"
"""


# --- Modalita' oracolare (TAG_MODE=oracolare) ---
# Il pensiero non e' ricondotto al suo argomento ma al momento che vive chi
# parla, scegliendo tra un vocabolario CHIUSO di 64 situazioni ispirate agli
# esagrammi dell'I Ching: le stelle della nebulosa esistono solo se i tag si
# ripetono, e un vocabolario aperto ne produrrebbe migliaia di uniche.
SITUAZIONI_PATH = Path(__file__).with_name("situazioni.json")
MAX_SITUAZIONI = 2

# La lista delle situazioni sta nel messaggio di sistema (uguale per ogni
# pensiero), cosi' Ollama ne tiene il prefisso in cache.
ORACLE_SYSTEM_PROMPT = """Sei un lettore oracolare nella tradizione dell'I Ching. \
Ricevi un pensiero detto a voce da una persona: spesso è parlato, a volte sgrammaticato.

Non ti interessa l'argomento di cui parla, ma il momento che sta vivendo chi parla: \
ciò che sta tra le righe, il moto nascosto sotto le parole, il tempo in cui si trova.

Scegli tra le 64 situazioni qui sotto quella che meglio coglie questo momento \
nascosto; aggiungine una seconda solo se è davvero necessaria. Diffida della \
situazione che si limita a ripetere l'argomento esplicito: se il pensiero parla \
di famiglia, raramente la risposta è La Famiglia.

Valuta anche quanto il testo sia "rumore di fondo": scritto a caso, una prova \
di scrittura, spazzatura o incomprensibile, senza un pensiero vero (un pensiero \
breve ma sensato NON è rumore di fondo, anche se generico).

Le 64 situazioni:
{lista}

Rispondi SOLO con un oggetto JSON con questa forma:
{{"situazioni": [numero, numero], "lettura": "una frase in italiano, al massimo \
25 parole, che dica che cosa c'è tra le righe", "rumore": 0.0}}

"rumore" è un numero da 0 (sicuramente un pensiero vero) a 1 (sicuramente \
rumore di fondo)."""

ORACLE_FORMAT = {
    "type": "object",
    "properties": {
        "situazioni": {"type": "array", "items": {"type": "integer"}},
        "lettura": {"type": "string"},
        "rumore": {"type": "number"},
    },
    "required": ["situazioni", "lettura", "rumore"],
}


@lru_cache(maxsize=1)
def _situazioni() -> dict[int, dict]:
    """Le 64 situazioni di backend/situazioni.json, per numero."""
    with open(SITUAZIONI_PATH, encoding="utf-8") as f:
        return {s["n"]: s for s in json.load(f)}


@lru_cache(maxsize=1)
def _oracle_system_prompt() -> str:
    lista = "\n".join(
        f"{s['n']}. {s['nome']}: {s['descrizione']}" for s in _situazioni().values()
    )
    return ORACLE_SYSTEM_PROMPT.format(lista=lista)


def _extract_situazioni(parsed) -> list[str]:
    """I tag (campo "tag" di situazioni.json) delle situazioni indicate nella
    risposta: tiene solo i numeri tra 1 e 64, senza duplicati, al massimo
    MAX_SITUAZIONI. Un numero fuori elenco o malformato viene scartato."""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("situazioni"), list):
        return []
    situazioni = _situazioni()
    tags: list[str] = []
    for value in parsed["situazioni"]:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        tag = situazioni.get(number, {}).get("tag")
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:MAX_SITUAZIONI]


def _extract_reading(parsed) -> str | None:
    if not isinstance(parsed, dict):
        return None
    reading = str(parsed.get("lettura") or "").strip()
    return reading or None


def _ask_ollama_for_reading(text: str) -> tuple[list[str], float, str | None]:
    """Situazioni (come tag), punteggio di rumore e lettura per un testo."""
    response = requests.post(
        f"{config.OLLAMA_HOST}/api/chat",
        json=ollama.generative({
            "model": config.OLLAMA_TAG_MODEL,
            "messages": [
                {"role": "system", "content": _oracle_system_prompt()},
                {"role": "user", "content": f'Pensiero:\n"""{text}"""'},
            ],
            "stream": False,
            "format": ORACLE_FORMAT,
            # Poca estro e seed fisso: lo stesso pensiero deve dare la stessa lettura.
            "options": {"temperature": 0.2, "seed": 42, "num_ctx": 16384},
        }),
        timeout=config.OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw = response.json()["message"]["content"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.debug("Risposta di Ollama non e' JSON valido: %r", raw)
        return [], 0.0, None
    tags = _extract_situazioni(parsed)
    if not tags:
        log.debug("Nessuna situazione estraibile dalla risposta di Ollama: %r", parsed)
    return tags, _extract_noise_score(parsed), _extract_reading(parsed)


def _extract_tags(parsed) -> list[str]:
    """Estrae una lista di tag da una risposta JSON di Ollama, tollerando
    forme diverse da quella richiesta (i modelli piccoli non sempre
    rispettano lo schema, es. {"natura": "ecologia"} invece di un array).
    """
    if isinstance(parsed, list):
        return [str(t) for t in parsed]
    if isinstance(parsed, dict):
        if isinstance(parsed.get("tags"), list):
            return [str(t) for t in parsed["tags"]]
        # fallback: appiattisce chiavi e valori come possibili tag
        flat = []
        for key, value in parsed.items():
            if key == "rumore":
                continue
            flat.append(str(key))
            if isinstance(value, list):
                flat.extend(str(v) for v in value)
            else:
                flat.append(str(value))
        return flat
    return []


def _extract_noise_score(parsed) -> float:
    """Il punteggio di rumore dichiarato da Ollama (vedi TAG_PROMPT), tra 0 e
    1; 0.0 se manca o non e' un numero (risposta malformata, o testo che il
    modello considera comunque un pensiero vero)."""
    if not isinstance(parsed, dict):
        return 0.0
    try:
        score = float(parsed.get("rumore", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return min(1.0, max(0.0, score))


def _ask_ollama_for_tags(text: str) -> tuple[list[str], float]:
    """Tag (fino a MAX_TAGS_PER_ENTRY) e punteggio di rumore per un testo."""
    prompt = TAG_PROMPT.format(text=text, max_tags=config.MAX_TAGS_PER_ENTRY)
    response = requests.post(
        f"{config.OLLAMA_HOST}/api/generate",
        json=ollama.generative({
            "model": config.OLLAMA_TAG_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }),
        timeout=config.OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    raw = response.json()["response"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Capita per testo spazzatura (vedi NOISE_TAG in tag_pending_entries):
        # un warning per ogni caso romperebbe la barra di avanzamento, quindi
        # resta a debug (LOG_LEVEL=DEBUG per vederlo).
        log.debug("Risposta di Ollama non e' JSON valido: %r", raw)
        return [], 0.0
    tags = _extract_tags(parsed)
    if not tags:
        log.debug("Nessun tag estraibile dalla risposta di Ollama: %r", parsed)
    return tags[: config.MAX_TAGS_PER_ENTRY], _extract_noise_score(parsed)


def tag_pending_entries() -> int:
    """Chiama Ollama per ogni entry non ancora taggata (o modificata dall'ultimo
    tagging). Ritorna il numero di entry taggate con successo.
    """
    entries = db_local.get_untagged_entries()
    total = db_local.count_entries()
    log.info(
        "%d entry da taggare su %d totali (le altre %d hanno gia' dei tag e "
        "vengono saltate), modalita' %s, modello '%s' su %s",
        len(entries),
        total,
        total - len(entries),
        config.TAG_MODE,
        config.OLLAMA_TAG_MODEL,
        config.OLLAMA_HOST,
    )
    if not entries:
        return 0

    tagged = 0
    noise = 0
    failed = 0
    progress = new_bar(len(entries), desc="Tagging", unit="entry")
    for entry in entries:
        try:
            if config.TAG_MODE == "oracolare":
                tags, score, reading = _ask_ollama_for_reading(entry["text"])
            else:
                tags, score = _ask_ollama_for_tags(entry["text"])
                reading = None
        except requests.RequestException as error:
            failed += 1
            log.debug(
                "Chiamata a Ollama fallita per entry id=%s (host %s raggiungibile?): %s",
                entry["id"], config.OLLAMA_HOST, error,
            )
            advance(progress, taggate=tagged, rumore=noise, errori=failed)
            continue
        if not tags:
            noise += 1
            tags = [NOISE_TAG]
        db_local.set_entry_tags(entry["id"], tags)
        db_local.set_noise_score(entry["id"], score)
        db_local.set_reading(entry["id"], reading)
        tagged += 1
        log.debug("entry id=%s -> tag %s (rumore %.2f)", entry["id"], tags, score)
        advance(progress, taggate=tagged, rumore=noise, errori=failed)
    progress.close()
    if failed:
        log.warning(
            "%d entry non taggate per errori di chiamata a Ollama (host %s raggiungibile?)",
            failed, config.OLLAMA_HOST,
        )
    if noise:
        log.info("%d entry senza tag estraibile, assegnate a '%s'", noise, NOISE_TAG)
    return tagged
