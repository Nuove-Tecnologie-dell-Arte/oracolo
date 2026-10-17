# Oracolo

Un sito che raccoglie pensieri anonimi (lasciati da persone, o presi da
libri, tesi e interviste) e li mostra come una **nebulosa di stelle**: ogni
stella è un tema che ricorre tra i pensieri. Entrando nel sito puoi fare una
domanda e un piccolo "Oracolo" (un'intelligenza artificiale) ti porta a
viaggiare tra le stelle finché non arrivi a quella più vicina al senso della
tua domanda, e lì ti risponde con una frase enigmatica, come farebbe una
sibilla.

## Cos'è, in parole semplici

- **I pensieri** arrivano da tre posti diversi: da un totem/stampante che
  raccoglie frasi anonime scritte dalle persone, da note caricate a mano
  (tesi, interviste), e da libri/tesi/interviste che l'Oracolo "legge" dalla
  cartella `testi/`.
- **Le stelle** sono i temi di questi pensieri (amore, paura, casa, mare...).
  Più persone parlano di un tema, più grande è la sua stella. Due stelle sono
  collegate da un filo se capita spesso che lo stesso pensiero tocchi
  entrambi i temi.
- **L'Oracolo** usa un'intelligenza artificiale (Ollama, che gira su un
  computer in rete, non su internet) per capire di cosa parla la tua domanda,
  scegliere la stella più adatta e scrivere una risposta ispirata ai
  pensieri raccolti lì.
- **Le categorie** (TUTTI / TESI / INTERVISTE / STAMPANTE) nell'header
  permettono di guardare solo una parte della nebulosa: per esempio solo i
  pensieri del totem, o solo le citazioni prese da tesi di laurea.

### Come si usa

Una volta avviato il server (vedi sotto), apri:

- `http://localhost:8000/` — la Nebulosa: scrivi una domanda (o scegline una
  suggerita), guarda la nebulosa portarti verso la stella giusta e leggi la
  risposta. Da lì puoi fare un'altra domanda o viaggiare liberamente: ogni
  stella che apri risponde alla tua domanda a modo suo. La stessa barra
  cerca anche i tag per nome.
- `http://localhost:8000/question.html` — "l'Oracolo": una domanda generata
  al volo, con un pulsante per cambiarla e uno per farsi dare una risposta
  criptica. Raggiungibile anche dalla stellina nell'header della Nebulosa.
- `http://localhost:8000/inserisci.html` — pannello per caricare in fretta
  file `.md` come pensieri in categoria tesi o interviste. Non richiede
  login: va bene in una rete di fiducia (casa, ufficio), non va messo
  online esposto a tutti.

### Installazione e avvio

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # poi compila le variabili (vedi i commenti nel file)
```

Carica anche [hosting/api/export.php](hosting/api/export.php) sul server web,
nella stessa cartella del `config.php` esistente (vedi il commento in testa
al file per l'unica cosa da adattare: il nome della tabella MySQL).

Per il frontend, la prima volta:

```bash
npm run frontend:install   # equivalente a: cd frontend && npm install
npm run build               # genera frontend/dist/, servito da `python -m backend.main serve`
```

I comandi `build`, `dev`, `lint` e `typecheck` nel `package.json` della
radice sono scorciatoie che restano nella home del progetto (non serve
`cd frontend`): delegano al `package.json` dentro `frontend/`.

Va ricostruito (`npm run build`) ogni volta che si modifica il codice React;
i dati (tag/pensieri) invece sono letti dal server Python a ogni richiesta,
quindi non serve ricompilare nulla quando cambiano solo i contenuti.

### Comandi disponibili

```bash
python -m backend.main sync      # scarica/aggiorna i pensieri dalla sorgente remota (MySQL)
python -m backend.main tag       # assegna i temi ai pensieri nuovi/modificati, via Ollama
python -m backend.main tag --retag  # come sopra, ma riprocessa anche i pensieri gia' taggati
python -m backend.main embed     # prepara i pensieri per l'Oracolo (calcola i vettori di similarità)
python -m backend.main ingest    # fa leggere all'Oracolo i PDF e i TXT nella cartella testi/
python -m backend.main pipeline  # sync + tag + embed, una volta
python -m backend.main run       # come pipeline, ma in loop ogni SYNC_INTERVAL_MINUTES
python -m backend.main serve     # avvia il webserver locale (frontend + API)
python -m backend.main seed      # inserisce dati di prova già taggati (per testare la nebulosa)
python -m backend.main export    # esporta una fotografia statica (HTML + JSON) per hosting solo PHP/HTML
```

### Testi letti dall'Oracolo

Oltre ai pensieri delle persone, l'Oracolo può leggere libri, tesi e
interviste. Metti i file (PDF o TXT) nella cartella `testi/` e lancia
`python -m backend.main ingest`:

- **tutto** il testo viene diviso in passi e finisce in una biblioteca che
  l'Oracolo consulta quando risponde;
- una **selezione** dei passi più rappresentativi (40 per testo, vedi
  `LIBRARY_STARS_PER_SOURCE` o `--stars`) entra nella nebulosa: da ognuno si
  prende una frase, citata alla lettera, che regga da sola come pensiero. I
  suoi temi vengono scelti tra quelli già presenti più vicini per significato,
  così la citazione si collega alle stelle esistenti; se nessun tema è
  abbastanza vicino nasce una stella nuova.

Le citazioni mostrano sempre autore e titolo. Si ricavano dal nome del file
(`Autore - Titolo.pdf`) oppure da `testi/fonti.json`:

```json
[{"file": "calvino.txt", "title": "Le citta' invisibili", "author": "Italo Calvino",
  "kind": "libro", "lines": [[45, 86], [1088, 2340]]}]
```

Campi facoltativi: `pages` (PDF) o `lines` (TXT) con gli intervalli da
leggere, per lasciare fuori indici, note editoriali e bibliografie che non
sono dell'autore; `stars`; `"kind": "tesi"` (non cita le frasi tra
virgolette, che in una tesi sono di altri autori); `"format": "interviste"`
per un file che raccoglie più interviste trascritte: ogni intervistato
diventa un autore, e contano solo le sue risposte.

I file dei testi non sono versionati (sono opere altrui): in git entra solo
`fonti.json`. `ingest --list` elenca i testi letti, `ingest --forget <file>`
ne toglie uno. I PDF fatti di sole immagini scansionate non contengono testo
e vanno prima convertiti.

Le citazioni con `"kind": "tesi"` o `"kind": "intervista"` finiscono nella
nebulosa con quella categoria (compaiono quindi anche filtrando per
TESI/INTERVISTE nell'header); i testi senza quel `kind` (es. `"libro"` o
nessun `kind`) restano visibili solo in TUTTI.

---

## Approfondimenti per nerd

### Struttura del progetto

```
backend/     backend Python: pipeline dati, logica dell'Oracolo, webserver
frontend/    frontend React/Vite ("La Nebulosa"): grafo interattivo + pagine statiche
hosting/     endpoint PHP da caricare sul server che ospita il DB MySQL
testi/       libri/tesi/interviste da far leggere all'Oracolo (non versionati, tranne fonti.json)
legacy/      residui del progetto Bolt.new/Supabase originale, non più in uso
```

### Flusso dei dati, end-to-end

1. **`sync`** (`backend/sync.py` + `backend/db_online.py`): scarica via HTTP
   tutte le righe da `hosting/api/export.php` (protetto da una API key
   condivisa, header `X-Api-Key`) e le upserta in SQLite locale
   (`backend/db_local.py`). Se il testo di una entry esistente è cambiato,
   `tagged_at` viene azzerato così verrà ritaggata.
2. **`tag`** (`backend/tagging.py`): per ogni entry con `tagged_at IS NULL`,
   chiede a Ollama (`OLLAMA_TAG_MODEL`, es. llama3.1) da 1 a
   `MAX_TAGS_PER_ENTRY` tag in JSON (`{"tags": [...]}`), tollerando risposte
   malformate (fallback che appiattisce chiavi/valori se il modello non
   rispetta lo schema).
3. **`embed`** (`backend/embeddings.py`): calcola, per ogni entry taggata, un
   vettore di embedding (`OLLAMA_EMBED_MODEL`, bge-m3) via `/api/embed`,
   normalizzato a lunghezza 1 e salvato come BLOB di float32. La similarità
   tra due vettori normalizzati è il semplice prodotto scalare (coseno).
   Gli embedding si (ri)calcolano solo se il testo o il modello sono
   cambiati (hash SHA-1 del testo + nome modello salvati insieme al vettore).
4. **`ingest`** (`backend/library.py` + `backend/themes.py`): legge PDF/TXT
   da `testi/`, li divide in **passi** (90–170 parole, senza spezzare le
   frasi), li salva tutti in `passages` (la "biblioteca" consultata per le
   risposte) e sceglie un sottoinsieme di **frasi citabili** da promuovere a
   entry della nebulosa (vedi sotto "Scelta delle citazioni").
5. **`graph`** (`backend/graph.py`): costruisce con NetworkX un grafo non
   orientato dove i nodi sono i tag (dimensione = quante entry li usano) e
   gli archi le co-occorrenze tra tag nella stessa entry; le componenti
   connesse diventano `cluster` (solo per colorare gruppi di tag nel
   frontend).
6. **`serve`** (`backend/server.py`): webserver HTTP basato su
   `http.server.ThreadingHTTPServer` (stdlib, nessun framework), che serve
   lo statico di `frontend/dist` e implementa le API sotto `/api/`.
7. **`export`** (`backend/export_static.py`): per un hosting solo
   PHP/HTML senza Python: builda il frontend con Vite (`--base=<path>`) e
   scrive uno snapshot JSON di `/api/graph` e `/api/tag/<nome>` come file
   statici — utile solo per una "fotografia" senza Oracolo (niente domande
   dinamiche, che richiedono il server Python + Ollama).

### Schema del DB locale (SQLite, `backend/db_local.py`)

- `entries(id, text, created_at, status, ip, likes, category, source_id, tagged_at, synced_at)`
  — `category` è una di `stampante|tesi|interviste|libro`, usata per i 4
  filtri del frontend. Gli id seguono uno schema per evitare collisioni tra
  provenienze diverse:
  - **positivi** = id della riga MySQL originale (sync);
  - **negativi, decrescenti da -1** = pensieri caricati a mano da
    `inserisci.html` (`insert_local_entries`);
  - **`FRAGMENT_ID_BASE` (1 000 000 000) + id del passo** = citazioni
    scelte da un testo letto (`insert_fragments`), per restare distinguibili
    dal passo di libreria d'origine.
- `tags(id, name)`, `entry_tags(entry_id, tag_id)` — relazione molti-a-molti.
- `entry_embeddings(entry_id, model, text_hash, vector)` — un vettore per
  entry, invalidato se cambia `model` o `text_hash`.
- `sources(id, file, title, author, kind, file_hash, added_at)` — un testo
  letto da `testi/`; `file_hash` resta vuoto finché l'ingest non è completo,
  così un caricamento interrotto a metà viene rifatto da capo al prossimo
  giro (vedi `finish_source`).
- `passages(id, source_id, position, text, model, vector)` — tutti i passi
  di un testo, con il proprio vettore: è la "biblioteca" che l'Oracolo
  consulta ma non mostra mai per intero.

### Scelta delle citazioni da un testo (`backend/library.py`)

Pipeline di lettura PDF/TXT pensata per restare fedele al testo (le frasi
mostrate non sono mai riscritte dal modello, solo scelte):

1. **Estrazione**: PDF via `pypdf` (modalità "layout" per evitare spazi
   finti dentro le legature tipografiche), TXT con fallback di encoding
   (`utf-8-sig` → `utf-8` → `cp1252` → `latin-1`).
2. **Ricostruzione del testo continuo** (`_flowing_text`): rimuove intestazioni
   /numeri di pagina ripetuti su molte pagine, ricuce le parole spezzate a
   fine riga, normalizza le legature tipografiche (ﬁ→fi, ecc.).
3. **Segmentazione in frasi** (`_sentences`): regex che non spezza dopo
   abbreviazioni note (`cfr.`, `pag.`, iniziali di nome...).
4. **Passi** (`split_passages`): accumula frasi fino a un minimo di 90
   parole, senza superare 170, scartando righe che non sembrano prosa
   (troppe cifre, troppi pochi caratteri alfabetici: tabelle, bibliografia).
5. **Frasi citabili** (`quotable_sentences`): tra 8 e 38 parole, iniziano
   maiuscole e finiscono con punteggiatura di chiusura, niente apparato
   critico (`cfr`, URL, DOI, numeri di pagina), parentesi/virgolette
   bilanciate; se il testo è una tesi, scarta le frasi tra virgolette
   (sono quasi sempre citazioni di altri autori, non pensiero dell'autore).
6. **Punteggio "tiene da sola come pensiero"** (`thought_score`): euristica
   basata sulla forma della frase, non sul significato — penalizza i verbi
   al passato (passato remoto/imperfetto, con una lista di eccezioni per
   non confondere "viva"/"attiva" con imperfetti), i nomi propri in mezzo
   alla frase (personaggi), le parole "meta" (capitolo, tabella...), gli
   inizi anaforici ("questo", "allora", "quindi"...); premia parole generali
   (vita, tempo, amore...), presente indicativo, seconda persona.
7. **Selezione per temi** (`_themes`, k-means semplificato su vettori
   normalizzati, inizializzazione far-point) + `choose_fragments`: individua
   i temi principali del testo e sceglie, per ciascuno, la frase con punteggio
   migliore tra i passi più vicini al centro di quel tema — così le citazioni
   scelte non si accavallano tutte sullo stesso argomento.
8. **Raccolte di interviste** (`read_interviews`): un file con più interviste
   trascritte (header `Fonte Audio N:`, `Intervistato/a: Nome (ruolo)`) viene
   diviso per intervistato; contano solo le sue risposte nella trascrizione
   fedele (sezione `TRASCRIZIONE`), non le sintesi scritte da altri.

Il parametro `INGEST_VERSION` in testa al file fa ripartire la lettura da
zero per **tutti** i testi se il metodo di lettura/scelta cambia; l'hash di
contenuto (`content_hash`) include titolo, autore, `stars` e testo, quindi
basta modificare `fonti.json` per far rileggere un file.

### Assegnazione dei temi alle citazioni (`backend/themes.py`)

Lasciare che il modello inventi liberamente i tag produce doppioni e temi
lunghi una riga. Si procede invece così:

1. `ThemeIndex` costruisce, dai pensieri delle *persone* (non dalle
   citazioni: altrimenti temi come "consapevolezza" si allargherebbero a
   dismisura), il **centro** di ogni tema già esistente (media dei vettori
   normalizzati delle entry che lo usano).
2. Per una nuova citazione, si cercano i temi il cui centro è più vicino per
   coseno, con un piccolo bonus ai temi più **specifici** (penalizza i temi
   onnipresenti: `specificity = log((totale+smoothing)/(usi_tag+smoothing))`)
   e si escludono i temi che hanno già la loro quota di citazioni
   (`QUOTE_SHARE_CAP`, minimo `QUOTE_CAP_MIN`), per non farsene monopolizzare
   pochi enormi.
3. Il modello generativo scorre fino a `CANDIDATES` temi vicini e ne scegli
   1–2 che descrivono davvero la frase (prompt con risposta JSON `{"temi": [...]}`).
4. Se nessun tema esistente è sopra la soglia `NEW_THEME_BELOW` (0.60 di
   coseno col più vicino), si chiede al modello di proporre fino a 3 parole
   nuove (un sostantivo comune, minuscolo); si tiene quella più vicina per
   significato alla frase, a meno che non sia già un tema esistente scritto
   in un'altra forma (gestito da `_existing`, con `difflib.get_close_matches`
   e confronto per accenti/plurali/radice comune) — in quel caso si riusa.

### L'Oracolo (`backend/oracle.py`)

- **`ask(question)`**: calcola l'embedding della domanda, trova gli `NEAREST`
  (8) pensieri più simili, e **classifica i tag** di quei pensieri
  (`_rank_tags`) pesandoli per quanto il pensiero supera il meno simile del
  gruppo, corretti per la "specificità" del tag nell'intera nebulosa (stesso
  principio log-smoothing di `themes.py`, per evitare che un tag onnipresente
  vinca sempre). Il tag con punteggio più alto è la stella di destinazione;
  i successivi 1–2 diventano il `path` (le stelle attraversate nel viaggio).
  Si consultano anche i passi della biblioteca più vicini (`_consult`) per
  arricchire il prompt e, eventualmente, mostrare una citazione letterale.
  Il tutto va in un prompt (`ANSWER_PROMPT`) che chiede a Ollama una sola
  frase, in italiano, in tono di sibilla.
- **`answer(question, tag)`**: la stessa risposta ma vista da una stella
  precisa (filtra le entry su quel tag); senza domanda, una "sentenza" sul
  tema della stella (`VOICE_PROMPT`).
- **`star_question`**: genera una domanda (non una risposta): una
  domanda-civetta mostrata accanto a una stella, che porta lì chi la sceglie.
  Ritenta fino a `QUESTION_ATTEMPTS` volte se il modello non rispetta le
  regole di forma (una sola frase, niente prima persona, non nomina il tema,
  lunghezza).
- **`suggestions()`**: pool di domande generate da Ollama, cache in memoria
  per `SUGGESTIONS_TTL` (10 minuti); se Ollama non risponde, usa
  `FALLBACK_SUGGESTIONS` e riprova dopo un minuto (non ad ogni richiesta).
- **Figure della costellazione** (`figure()`): mentre il visitatore
  viaggia, il frontend (`constellation.ts`/`figures.ts`) disegna una forma
  (cuore, nave, montagna...) scelta in base a quale `FIGURES[...]` ha il
  significato più vicino, per coseno, all'insieme delle domande fatte e dei
  tag attraversati; `FIGURE_PROMPT` genera la frase di rivelazione finale,
  scartando risposte in prima persona o con appellativi (`_CALLING`).

Tutte le chiamate generative passano da `requests` con timeout
(`OLLAMA_TIMEOUT_SECONDS`); solo `embeddings.py`/`themes.py` passano dal
wrapper `backend/ollama.py` che **ritenta** con pause crescenti (2s, 5s, 15s)
sulle chiamate di embedding e assegnazione temi, utili nei job lunghi di
`ingest`.

### API HTTP (`backend/server.py`)

Server minimale su stdlib (`ThreadingHTTPServer` + `SimpleHTTPRequestHandler`),
senza framework: ogni richiesta `/api/...` passa da `_guarded`, che intercetta
qualunque eccezione e la trasforma in una risposta JSON 500 leggibile invece
di chiudere la connessione.

| Metodo | Path | Descrizione |
| --- | --- | --- |
| GET | `/api/graph?category=<tutti\|tesi\|interviste\|stampante>` | nodi (tag) e archi (co-occorrenze) del grafo |
| GET | `/api/tag/<nome>?category=<...>` | frammenti e tag collegati per un singolo tag |
| GET | `/api/noise?category=<...>&min_score=<0-1>` | entry col punteggio di rumore (vedi `backend/tagging.py`) almeno `min_score` (default 0.5): alimenta i nodi-messaggio del pulsante dedicato nell'header, la cui soglia si regola con +/- |
| GET | `/api/questions` | domande evocative generate al volo (`question.html`) |
| GET | `/api/suggestions` | domande da proporre a chi entra |
| GET | `/api/oracle/star-question?tag=<nome>&asked=<domanda precedente>` | domanda-civetta che rappresenta una stella (diversa ogni volta) |
| GET | `/api/health` | stato del server, di Ollama (modelli presenti/mancanti) e della biblioteca |
| POST | `/api/ask` `{"question"}` | domanda del visitatore: stella di destinazione, path, risposta, pensieri e citazioni |
| POST | `/api/answer` `{"question"?, "tag"?}` | testo oracolare di una stella (risposta o sentenza) |
| POST | `/api/oracle/figure` `{"questions", "tags", "exclude"?, "figure"?, "speak"?}` | figura disegnata dal viaggio + eventuale rivelazione |
| POST | `/api/upload` `{"category": "tesi"\|"interviste", "files": [{"filename","text"}]}` | carica entry testuali, le tagga subito e ritorna `{"inserted","tagged"}` |

`GET /api/health` è pensato per il debug "a colpo d'occhio": controlla se
Ollama è raggiungibile, se i modelli configurati (`OLLAMA_TAG_MODEL`,
`OLLAMA_EMBED_MODEL`) sono effettivamente presenti sul server Ollama, e se
ci sono entry taggate — con un messaggio in chiaro su cosa manca.

### Configurazione (`backend/config.py`, vedi `.env.example`)

Tutte le variabili sono lette da `.env` (via `python-dotenv`) con default
sensati. Degna di nota `_ollama_url`: normalizza `OLLAMA_HOST` replicando
la logica del client ufficiale di Ollama (aggiunge schema/porta se mancanti,
e se il valore è `0.0.0.0`/`::` — tipico quando la stessa variabile è usata
per far ascoltare Ollama su tutte le interfacce — lo riscrive come
`127.0.0.1`, altrimenti il Python locale proverebbe a connettersi a un
indirizzo che non è un host valido).

### Frontend (`frontend/`)

Vite + React + TypeScript, in origine generato da un progetto Bolt.new su
Supabase (da cui il residuo in `legacy/supabase/`, non più collegato a
nulla: il frontend legge oggi in sola lettura le API del backend Python).

- `src/App.tsx` — stato dell'app, routing dei pannelli (grafo / dettaglio
  tag / domande), filtro di categoria da query string (`?category=`).
- `src/lib/api.ts` — client tipizzato delle API REST sopra; usa
  `import.meta.env.BASE_URL` come prefisso, così le stesse chiamate
  funzionano sia servite dal webserver Python locale sia dall'export
  statico con un `base` diverso.
- `src/constellation.ts` / `src/figures.ts` / `src/shapes.ts` — logica del
  "viaggio" tra le stelle e disegno delle figure della costellazione
  (`react-force-graph-2d`/`-3d` per il layout del grafo).
- `src/components/TagDetail{Modal,Panel}.tsx` — pannello di dettaglio di una
  stella (pensieri + tag collegati).
- `public/question.html`, `public/inserisci.html` — pagine statiche
  indipendenti dalla SPA principale, servite direttamente dal webserver.

### Note operative

- `OLLAMA_EMBED_MODEL` (bge-m3) misura la similarità di significato tra una
  domanda e i pensieri: serve all'Oracolo per scegliere la stella e i
  pensieri a cui ispirarsi. I vettori delle entry si calcolano da soli alla
  prima domanda (qualche decina di secondi) e restano nel DB locale.
  `OLLAMA_TAG_MODEL` (un modello generativo, es. llama3.1) scrive i temi, le
  domande e le risposte.
- Il DB locale (`data/local.db`) non è versionato: verrà ricreato al primo
  `sync` (schema in `backend/db_local.py`, con migrazioni leggere in
  `init_db` per i DB creati da versioni precedenti del progetto).
- `legacy/supabase/` è un residuo del progetto Bolt.new/Supabase originale:
  non è più letto da nessuna parte del codice, tenuto solo per memoria
  storica.
