"""Piccole funzioni sul testo usate da piu' moduli."""

import unicodedata


def plain(text: str) -> str:
    """Minuscolo e senza accenti: "liberta" e "libertà" sono la stessa parola."""
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(ch)
    )
