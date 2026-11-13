"""Il ciclo `run` non deve fermarsi per un errore di un giro (diario o
stampante giu', Ollama irraggiungibile): lo scrive nel log e riprova al giro
successivo."""

import argparse

import requests

from backend import main


def test_un_giro_fallito_non_ferma_il_ciclo(monkeypatch):
    def guasto(_args):
        raise requests.ConnectionError("diario spento")

    monkeypatch.setattr(main, "do_pipeline", guasto)
    assert main.safe_pipeline(argparse.Namespace(retag=False)) is False


def test_un_giro_riuscito(monkeypatch):
    chiamate = []
    monkeypatch.setattr(main, "do_pipeline", chiamate.append)
    assert main.safe_pipeline(argparse.Namespace(retag=False)) is True
    assert len(chiamate) == 1
