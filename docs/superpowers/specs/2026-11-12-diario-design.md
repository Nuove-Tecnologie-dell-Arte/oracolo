# Diario di bordo nella Nebulosa — design

Data: 2026-11-12 · Branch: `diario`

## Obiettivo

Aggiungere all'Oracolo una nuova provenienza di pensieri, **il Diario di
bordo** (https://diario.nuovetecnologiedellarte.it/), che funzioni come la
stampante: i pensieri del diario diventano stelle della nebulosa, hanno un
filtro **DIARIO** nell'header e compaiono anche in TUTTI. Sotto ogni
pensiero del diario si legge il gruppo di chi l'ha scritto ("— 4° anno",
"— Docenti").

Riuscito quando: dopo `sync` + `tag` (+ `embed`) i pensieri reali del diario
sono stelle, `?category=diario` mostra solo loro, la scheda di una stella
mostra il gruppo sotto ciascun pensiero del diario, e un diario
irraggiungibile non rompe né svuota nulla.

## Cosa offre il diario

API pubblica in JSON, senza chiave:

- `GET /api/pensieri?pagina=N&per_pagina=M` →
  `{"totale", "pagina", "pagine", "pensieri": [{"id", "testo", "categoria", "giorno"}]}`,
  dal più recente; `categoria` è la chiave del gruppo (`anno-4`, `docenti`…),
  `giorno` è `AAAA-MM-GG`.
- `GET /api/categorie` →
  `{"categorie": [{"chiave", "nome", "conteggio"}], "testo_max"}`: il nome
  leggibile di ogni gruppo (`anno-4` → "4° anno").

Al 2026-11-12: 36 pensieri, 8 gruppi.

## Approccio

Un modulo dedicato `backend/diario.py` che legge l'API del diario e la porta
nel DB locale. Scartati: un sistema generico di "sorgenti" configurabili
(due sorgenti con formati diversi non lo giustificano) e un `export.php` sul
server del diario (l'API pubblica esiste già).

## Dati

- **Categoria**: `entries.category = 'diario'`.
- **Id**: `DIARIO_ID_BASE + id del diario`, con `DIARIO_ID_BASE =
  2_000_000_000`. È una fascia nuova, distinta da quelle fissate nel
  CLAUDE.md (positivi = MySQL della stampante, negativi = `inserisci.html`,
  `FRAGMENT_ID_BASE (1_000_000_000) + id passo` = citazioni). Il CLAUDE.md
  va aggiornato con la nuova fascia.
- **Gruppo**: nuova colonna `entries.gruppo TEXT` (NULL per tutto ciò che
  non viene dal diario), aggiunta in `init_db` con lo stesso schema di
  migrazione già usato per `category`/`noise_score`. Contiene il **nome
  leggibile** ("4° anno"), preso da `/api/categorie`; se una chiave non è in
  quell'elenco si salva la chiave stessa.
- **Data**: `giorno` → `created_at`.
- `status`, `ip` restano NULL; `likes` = 0.

Il gruppo **non** va in `source`: `source` significa "citazione tratta da un
testo" e `themes.py` lo usa per riconoscere le citazioni. Il gruppo viaggia
in un campo a sé, `group`.

## Sincronizzazione

`backend/diario.py`:

- `fetch_pensieri()` scarica tutte le pagine di `/api/pensieri` (pagine da
  100) e i nomi da `/api/categorie`; timeout `REMOTE_API_TIMEOUT_SECONDS`.
- `to_entries(pensieri, nomi)` (funzione pura, testabile senza rete)
  trasforma i pensieri nel formato di `db_local`: id con la base, testo,
  `created_at`, `gruppo`.
- `run_sync_diario()` fa l'upsert e la **pulizia**: le entry `diario` locali
  il cui id non è più nell'elenco scaricato vengono cancellate (con i loro
  tag ed embedding, via `ON DELETE CASCADE`). La pulizia avviene solo se lo
  scaricamento è andato a buon fine per intero.

Nuova funzione in `db_local`: `upsert_diario_entries(rows)` (come
`upsert_entries`, ma scrive anche `category` e `gruppo`; se il testo cambia
azzera `tagged_at`) e `delete_diario_entries_except(ids)`.

Configurazione: `DIARIO_API_URL` in `config.py`/`.env.example`, default
`https://diario.nuovetecnologiedellarte.it`; vuoto = diario disattivato.

`sync.run_sync()` scarica **stampante e diario in modo indipendente**: un
errore su una sorgente viene scritto nel log e non ferma l'altra. La
stampante viene saltata (con un messaggio) se `REMOTE_API_URL` è vuoto.
`run_sync()` ritorna il totale delle entry sincronizzate; se **entrambe** le
sorgenti falliscono solleva l'errore come oggi, così `run` lo vede.

`tag`, `embed`, `pipeline` e `run` non cambiano: lavorano già su tutte le
entry senza tag/vettore, di qualunque categoria.

## Server

- `db_local.get_entries_with_tags` restituisce anche `group` (da
  `e.gruppo`).
- `tagdetail.build_tag_detail` e `oracle` (`_thought`, riga ~171) includono
  `group` accanto a `source` in ogni entry serializzata.
- Il filtro `?category=diario` funziona già (`_category_filter` passa la
  stringa così com'è); la docstring di `get_entries_with_tags` va
  aggiornata con `'diario'`.

## Frontend

- `lib/api.ts`: `Category` include `'diario'`; `TagEntry`, le entries di
  `RelatedTag` e `OracleThought` hanno `group?: string | null`.
- `categories.ts`: nuova opzione `{ value: 'diario', label: 'Diario' }`
  dopo Stampante.
- `TagDetailPanel.tsx`: accanto ad `Attribution` (autore, titolo) una
  firma del gruppo, `<cite className="reply-source">4° anno</cite>`, con lo
  stesso stile (trattino lungo davanti). Compare ovunque compare oggi
  `Attribution`: frammenti, pensieri ascoltati, stelle vicine, pensiero
  offerto da una stella muta. Il gruppo è testo semplice, senza corsivo.
- Header: con cinque filtri lo spazio su mobile va verificato (oggi
  `.category-tabs` usa `justify-content: space-between`).

## Errori

- Diario irraggiungibile, risposta non JSON o pagina mancante: log
  dell'errore, nessuna scrittura e **nessuna pulizia** (un sito spento non
  deve svuotare la nebulosa); la stampante prosegue.
- Pensiero con testo vuoto: scartato.
- Chiave di gruppo sconosciuta: salvata la chiave così com'è.

## Test

- `tests/test_diario.py` (pytest, senza rete):
  - `to_entries`: id con la base, gruppo leggibile, chiave sconosciuta,
    testo vuoto scartato, `giorno` → `created_at`;
  - paginazione di `fetch_pensieri` con una sessione HTTP finta (tutte le
    pagine lette; errore a metà = eccezione, quindi niente pulizia);
  - upsert + pulizia su un DB SQLite temporaneo (`LOCAL_DB_PATH` in una
    cartella temporanea): un pensiero sparito viene tolto, uno con testo
    cambiato perde `tagged_at`, le altre categorie non vengono toccate.
- Prova vera: `sync` (diario reale, 36 pensieri) + `tag` + `embed` con
  Ollama del computersopra via tunnel, poi `?category=diario` nel browser,
  scheda di una stella con il gruppo sotto i pensieri, a desktop e mobile.
- `npm run typecheck`, `npm run lint`, `npm run build`, `python -m pytest`.

## Fuori da questo lavoro

- Sotto-filtri per gruppo (solo docenti, solo un anno): possibile in
  seguito, il dato `gruppo` è già salvato.
- Aggiornamento in tempo reale: il diario entra con il ciclo di `sync`
  (`run` ogni `SYNC_INTERVAL_MINUTES`), come la stampante.
