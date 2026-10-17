# CLAUDE.md

Guida per Claude Code (e per chi riprende questo progetto) su struttura,
convenzioni e comandi di Oracolo. Per la descrizione del progetto e i
dettagli tecnici vedi [README.md](README.md) (ha anche una sezione
"Approfondimenti per nerd" con l'architettura in dettaglio).

## Struttura

```
backend/     backend Python (pipeline dati, logica dell'Oracolo, webserver stdlib)
frontend/    frontend React/Vite ("La Nebulosa"), buildato in frontend/dist
scripts/     script di shell per lavori lunghi sul lab (es. `tagga-oracolare.sh`)
hosting/     endpoint PHP da caricare sul server che espone il DB MySQL
testi/       libri/tesi/interviste letti dall'Oracolo (non versionati, tranne fonti.json)
legacy/      residui del progetto Bolt.new/Supabase originale, non più in uso
data/        DB SQLite locale (non versionato, ricreato da `sync`)
```

- Il backend si importa come `backend.<modulo>` (es. `from backend import config`),
  mai `src.*`: la cartella si chiamava `src/` prima di un rename, non deve
  tornare a comparire in import o riferimenti.
- Il frontend è in `frontend/`, non più `layoutBoltNebulosa/project/`: stesso
  discorso, non reintrodurre quel path nei comandi o nella doc.

## Comandi principali

```bash
python -m backend.main sync|tag|embed|ingest|pipeline|run|serve|seed|export
```

Vedi README per il significato di ciascuno. Per lavorare sul frontend:

```bash
cd frontend && npm install && npm run build   # build servita da `backend.main serve`
cd frontend && npm run dev                     # dev server Vite (non legge le API locali a meno di proxy)
cd frontend && npm run lint && npm run typecheck
```

## Convenzioni di codice

- **Lingua**: commenti, docstring, messaggi di log e testi del frontend sono
  in italiano. Mantenere questa convenzione nel codice esistente; va bene
  scrivere in inglese solo se è già la lingua dominante di un file nuovo e
  isolato (non è il caso qui).
- **Niente framework web lato backend**: il server (`backend/server.py`) usa
  solo `http.server` della stdlib. Non introdurre Flask/FastAPI senza che sia
  una decisione esplicita e discussa: è una scelta voluta per restare senza
  dipendenze pesanti su un progetto piccolo.
- **ID delle entry in `backend/db_local.py`** seguono uno schema per evitare
  collisioni tra provenienze diverse: positivi = righe MySQL, negativi
  (decrescenti da -1) = upload manuali da `inserisci.html`, `FRAGMENT_ID_BASE
  (1_000_000_000) + id passo` = citazioni tratte da un testo. Non riusare
  questi intervalli per altro.
- **Le citazioni dai testi non vengono mai riscritte dal modello**: solo
  selezionate (vedi `backend/library.py`, `quotable_sentences`/`thought_score`).
  Se si modifica questa pipeline, mantenere l'invariante: il testo mostrato
  come citazione deve essere letterale.
- **`INGEST_VERSION`** in `backend/library.py` va incrementato ogni volta che
  cambia il modo di leggere/segmentare/scegliere i testi, per forzare un
  re-ingest completo al prossimo `ingest`.
- **I tag/temi sono sempre minuscoli** e normalizzati (vedi `_plain`/`_existing`
  in `backend/themes.py` per accenti, plurali, varianti): non introdurre tag
  con maiuscole o duplicati evidenti senza passare da quella logica.

## Test e verifica

Non c'è una suite di test automatizzata. Per verificare un cambiamento:
- `python -m backend.main seed` per popolare il DB locale senza bisogno di
  MySQL/Ollama, poi `python -m backend.main serve` e controllare a occhio
  `http://localhost:8000/`.
- Le funzionalità che dipendono da Ollama (tag, embed, Oracolo) richiedono
  un'istanza Ollama raggiungibile (`OLLAMA_HOST` in `.env`); senza, `seed` +
  `serve` mostrano comunque il grafo (ma non le risposte dell'Oracolo).
- `GET /api/health` dice in chiaro cosa manca (Ollama irraggiungibile,
  modelli assenti, nessuna entry taggata).

## Git

- Il push è sempre a carico dell'utente: non eseguire `git push` da solo
  anche se la modifica sembra innocua. Commit locali vanno bene se richiesti
  esplicitamente.
