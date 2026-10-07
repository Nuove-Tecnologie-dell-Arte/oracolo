"""Test sulle funzioni pure di backend/themes.py. ThemeIndex viene
costruito bypassando __init__ (che legge dal DB locale) e impostando a
mano gli attributi che i metodi usano: i metodi testati qui non toccano
mai il DB o Ollama.
"""

from backend.themes import ThemeIndex, _existing, _plain


def _empty_index() -> ThemeIndex:
    index = ThemeIndex.__new__(ThemeIndex)
    index._sums = {}
    index._centers = {}
    index._uses = {}
    index._total = 0
    index._quote_uses = {}
    index._quotes = 0
    return index


class TestPlain:
    def test_toglie_gli_accenti(self):
        assert _plain("libertà") == "liberta"
        assert _plain("perché") == "perche"


class TestExisting:
    def test_stessa_parola_con_accento_diverso(self):
        assert _existing("cittadina", ["città"]) == "città"

    def test_plurale_di_un_tema_esistente(self):
        assert _existing("memorie", ["memoria"]) == "memoria"

    def test_desinenza_diversa_via_prefisso_condiviso(self):
        # Esempio dal docstring di ThemeIndex: sciamano / sciamanesimo.
        assert _existing("sciamanesimo", ["sciamano"]) == "sciamano"

    def test_parola_senza_nessun_tema_simile_resta_se_stessa(self):
        assert _existing("completamentenuovo", ["altro", "casa"]) == "completamentenuovo"


class TestThemeIndex:
    def test_nearest_mette_prima_il_tema_piu_vicino(self):
        index = _empty_index()
        index.add("amore", [1.0, 0.0])
        index.add("paura", [0.0, 1.0])
        nearest = index.nearest([0.9, 0.1], 2)
        assert nearest[0][1] == "amore"
        assert nearest[1][1] == "paura"

    def test_contains_solo_i_temi_aggiunti(self):
        index = _empty_index()
        index.add("amore", [1.0, 0.0])
        assert "amore" in index
        assert "gioia" not in index

    def test_full_scatta_dopo_il_tetto_di_citazioni(self):
        index = _empty_index()
        assert not index.full("amore")
        for _ in range(10):
            index.add_quote(["amore"])
        assert index.full("amore")

    def test_specificity_e_piu_alta_per_un_tema_raro(self):
        index = _empty_index()
        index._uses = {"comune": 100, "raro": 1}
        index._total = 101
        assert index._specificity("raro") > index._specificity("comune")
