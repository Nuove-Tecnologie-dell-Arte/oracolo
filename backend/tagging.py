import json

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
    raw = ollama.generate(prompt, json_format=True)
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
        "vengono saltate), modello '%s' su %s",
        len(entries),
        total,
        total - len(entries),
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
            tags, score = _ask_ollama_for_tags(entry["text"])
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
