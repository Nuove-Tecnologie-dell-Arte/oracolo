"""Chiamate a Ollama che riprovano quando la connessione cade.

Nei lavori lunghi (leggere un libro intero) basta una caduta di rete di un
istante per perdere tutto: qui una richiesta fallita viene ritentata qualche
volta, con una pausa crescente, prima di arrendersi.
"""

import time

import requests

from backend import config
from backend.logging_utils import get_logger

log = get_logger(__name__)

# Pause (in secondi) prima di ogni nuovo tentativo.
RETRY_PAUSES = (2, 5, 15)


def generate(prompt: str, temperature: float | None = None, json_format: bool = False) -> str:
    """Testo generato da Ollama per `prompt` (con `json_format` obbliga il
    modello a rispondere in JSON). Un solo tentativo: serve a chi risponde a
    una richiesta in corso, che non puo' aspettare i tentativi di `post`."""
    payload: dict = {"model": config.OLLAMA_TAG_MODEL, "prompt": prompt, "stream": False}
    if json_format:
        payload["format"] = "json"
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    response = requests.post(
        f"{config.OLLAMA_HOST}/api/generate",
        json=payload,
        timeout=config.OLLAMA_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["response"]


def post(endpoint: str, payload: dict) -> dict:
    """POST a Ollama (es. "/api/embed"); ritorna la risposta JSON. Riprova
    se la connessione cade, scade il tempo o Ollama risponde con un errore
    temporaneo (5xx)."""
    for attempt, pause in enumerate((*RETRY_PAUSES, None), start=1):
        try:
            response = requests.post(
                f"{config.OLLAMA_HOST}{endpoint}",
                json=payload,
                timeout=config.OLLAMA_TIMEOUT_SECONDS,
            )
            if response.status_code < 500:
                response.raise_for_status()
                return response.json()
            error: Exception = requests.HTTPError(f"errore {response.status_code}", response=response)
        except (requests.ConnectionError, requests.Timeout) as failure:
            error = failure
        if pause is None:
            raise error
        log.warning("Ollama non ha risposto (tentativo %d): riprovo tra %ds", attempt, pause)
        time.sleep(pause)
    raise RuntimeError("irraggiungibile")  # mai: il ciclo ritorna o solleva
