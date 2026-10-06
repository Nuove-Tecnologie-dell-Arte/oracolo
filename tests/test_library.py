"""Test sulle funzioni pure di backend/library.py: nessun Ollama/DB
coinvolto, solo testo. Vedi CLAUDE.md: le citazioni non vengono mai
riscritte, solo selezionate - e' l'invariante che quotable_sentences deve
rispettare sempre.
"""

from backend.library import _is_past, _sentences, quotable_sentences, thought_score


class TestSentences:
    def test_non_spezza_dopo_un_abbreviazione(self):
        paragrafo = "Il dott. Rossi disse qualcosa. Poi se ne andò in silenzio verso casa."
        assert _sentences(paragrafo) == [
            "Il dott. Rossi disse qualcosa.",
            "Poi se ne andò in silenzio verso casa.",
        ]

    def test_non_spezza_dopo_un_iniziale_puntata(self):
        paragrafo = "Ho incontrato M. Rossi oggi. Era gentile."
        assert _sentences(paragrafo) == [
            "Ho incontrato M. Rossi oggi.",
            "Era gentile.",
        ]

    def test_spezza_normalmente_tra_due_frasi(self):
        paragrafo = "Questa è la prima frase. Questa è la seconda."
        assert _sentences(paragrafo) == [
            "Questa è la prima frase.",
            "Questa è la seconda.",
        ]


class TestIsPast:
    def test_riconosce_imperfetto_e_passato_remoto(self):
        for word in ["era", "cantava", "disse", "visse", "venne"]:
            assert _is_past(word), word

    def test_non_scambia_presente_per_passato(self):
        for word in ["è", "corre", "significa"]:
            assert not _is_past(word), word

    def test_non_cade_nelle_eccezioni_che_sembrano_passato(self):
        # "pero'", "lunedi'" ecc. finiscono per vocale accentata come certi
        # passati remoti, ma non lo sono.
        for word in ["però", "lunedì", "così"]:
            assert not _is_past(word), word


class TestThoughtScore:
    def test_premia_una_frase_generale_al_presente(self):
        frase = "Ogni persona porta con sé un mondo che nessuno conosce davvero."
        assert thought_score(frase) > 0

    def test_penalizza_pesantemente_il_racconto_al_passato(self):
        frase = "Quella sera camminò a lungo senza una meta precisa nella città deserta."
        assert thought_score(frase) == -5


class TestQuotableSentences:
    """Vedi CLAUDE.md: il testo mostrato come citazione deve essere
    letterale. Qui si verifica proprio questo: quotable_sentences non deve
    mai restituire una frase che non sia, parola per parola, dentro il
    passo originale."""

    PASSAGE = (
        "La vita è fatta di piccoli momenti che restano, anche quando tutto "
        "il resto sbiadisce. "
        "Nel 2020 la vita di molte persone cambiò improvvisamente e per sempre. "
        "Corto. "
        "Ogni scelta che facciamo oggi costruisce la persona che diventeremo domani."
    )

    def test_ogni_frase_restituita_e_letterale_nel_passo(self):
        quotable = quotable_sentences(self.PASSAGE)
        assert quotable  # la lista di esempio ne contiene almeno una
        for sentence in quotable:
            assert sentence in self.PASSAGE

    def test_scarta_frasi_con_cifre(self):
        quotable = quotable_sentences(self.PASSAGE)
        assert not any("2020" in s for s in quotable)

    def test_scarta_frasi_troppo_corte(self):
        quotable = quotable_sentences(self.PASSAGE)
        assert not any(s.strip() == "Corto." for s in quotable)

    def test_in_una_tesi_scarta_le_citazioni_tra_virgolette(self):
        passo = "Come scrive l'autore, «il senso della vita sfugge a chi lo insegue con troppa fretta»."
        assert quotable_sentences(passo, kind="tesi") == []
        assert quotable_sentences(passo, kind=None) != []
