import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from backend import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,          -- stesso id della riga MySQL
    text TEXT NOT NULL,
    created_at TEXT,
    status TEXT,
    ip TEXT,
    likes INTEGER,
    -- 'stampante' (pensieri dal totem), 'tesi'/'interviste' (caricate a mano
    -- o lette da un testo con quel kind), 'libro' (testi letti senza kind
    -- tesi/intervista): usata per filtrare la nebulosa per categoria.
    category TEXT NOT NULL DEFAULT 'stampante',
    synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
    tagged_at TEXT                   -- NULL finche' Ollama non l'ha ancora processata
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS entry_tags (
    entry_id INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (entry_id, tag_id)
);

CREATE TABLE IF NOT EXISTS entry_embeddings (
    entry_id INTEGER PRIMARY KEY REFERENCES entries(id) ON DELETE CASCADE,
    model TEXT NOT NULL,             -- modello che ha prodotto il vettore
    text_hash TEXT NOT NULL,         -- impronta del testo: se cambia va ricalcolato
    vector BLOB NOT NULL             -- vettore normalizzato, float a 32 bit
);

-- Testi dati in lettura all'Oracolo (libri, tesi, interviste): vedi library.py
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL UNIQUE,       -- nome del file nella cartella dei testi
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    kind TEXT,                       -- libro, tesi, intervista...
    file_hash TEXT NOT NULL,         -- impronta del file: se cambia va riletto
    added_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Tutti i passi di un testo: la "biblioteca" che l'Oracolo consulta.
CREATE TABLE IF NOT EXISTS passages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,       -- ordine nel testo
    text TEXT NOT NULL,
    model TEXT,                      -- modello che ha prodotto il vettore
    vector BLOB                      -- vettore normalizzato, float a 32 bit
);
"""

# Le citazioni scelte dai testi entrano nella nebulosa come entry, accanto ai
# pensieri delle persone. I loro id partono da qui, per non scontrarsi con
# quelli delle righe MySQL: id = FRAGMENT_ID_BASE + id del passo d'origine.
FRAGMENT_ID_BASE = 1_000_000_000


@contextmanager
def get_connection():
    Path(config.LOCAL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.LOCAL_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        # DB creati prima dei testi: alle entry manca la colonna della fonte
        # (NULL = pensiero di una persona).
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(entries)")}
        if "source_id" not in columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN source_id INTEGER "
                "REFERENCES sources(id) ON DELETE CASCADE"
            )
        if "category" not in columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN category TEXT NOT NULL DEFAULT 'stampante'"
            )
        if "noise_score" not in columns:
            # Da 0 (sicuramente un pensiero vero) a 1 (sicuramente rumore di
            # fondo), assegnato da Ollama in fase di tag (vedi backend/tagging.py).
            # NULL finche' l'entry non e' stata (ri)taggata con questo campo.
            conn.execute("ALTER TABLE entries ADD COLUMN noise_score REAL")


def upsert_entries(rows: list[dict]) -> int:
    """Inserisce o aggiorna le entry sincronizzate da MySQL.

    Se il testo di un'entry esistente cambia, azzera tagged_at cosi'
    verra' ritaggata al prossimo giro.
    """
    if not rows:
        return 0
    with get_connection() as conn:
        for row in rows:
            existing = conn.execute(
                "SELECT text FROM entries WHERE id = ?", (row["id"],)
            ).fetchone()
            text_changed = existing is not None and existing["text"] != row["text"]
            conn.execute(
                """
                INSERT INTO entries (id, text, created_at, status, ip, likes)
                VALUES (:id, :text, :created_at, :status, :ip, :likes)
                ON CONFLICT(id) DO UPDATE SET
                    text = excluded.text,
                    created_at = excluded.created_at,
                    status = excluded.status,
                    ip = excluded.ip,
                    likes = excluded.likes,
                    synced_at = CURRENT_TIMESTAMP
                """,
                row,
            )
            if text_changed:
                conn.execute(
                    "UPDATE entries SET tagged_at = NULL WHERE id = ?", (row["id"],)
                )
    return len(rows)


def insert_local_entries(category: str, texts: list[str]) -> list[int]:
    """Inserisce entry caricate a mano dal pannello /inserisci.html (tesi o
    interviste), con id negativi cosi' non collidono mai con quelli delle
    righe MySQL (positivi) o delle citazioni dai testi (>= FRAGMENT_ID_BASE)."""
    if category not in ("tesi", "interviste"):
        raise ValueError(f"categoria non valida per inserimento locale: {category!r}")
    if not texts:
        return []
    with get_connection() as conn:
        next_id = (conn.execute("SELECT MIN(id) AS m FROM entries").fetchone()["m"] or 0) - 1
        if next_id >= 0:
            next_id = -1
        ids = []
        for text in texts:
            conn.execute(
                """
                INSERT INTO entries (id, text, created_at, status, ip, likes, category)
                VALUES (?, ?, NULL, 'uploaded', NULL, 0, ?)
                """,
                (next_id, text, category),
            )
            ids.append(next_id)
            next_id -= 1
    return ids


def count_entries() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM entries").fetchone()["n"]


def get_untagged_entries() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, text FROM entries WHERE tagged_at IS NULL"
        ).fetchall()


def reset_all_tagged() -> int:
    """Azzera tagged_at su tutte le entry gia' taggate, cosi' il prossimo
    'tag' le riprocessa da capo (serve per ricalcolare noise_score sulle
    entry taggate prima che esistesse, o dopo un cambio di modello/prompt).
    Ritorna quante ne ha azzerate."""
    with get_connection() as conn:
        return conn.execute(
            "UPDATE entries SET tagged_at = NULL WHERE tagged_at IS NOT NULL"
        ).rowcount


def set_entry_tags(entry_id: int, tag_names: list[str]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
        for name in tag_names:
            name = name.strip().lower()
            if not name:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,)
            )
            tag_id = conn.execute(
                "SELECT id FROM tags WHERE name = ?", (name,)
            ).fetchone()["id"]
            conn.execute(
                "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                (entry_id, tag_id),
            )
        conn.execute(
            "UPDATE entries SET tagged_at = CURRENT_TIMESTAMP WHERE id = ?",
            (entry_id,),
        )


def set_noise_score(entry_id: int, score: float) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE entries SET noise_score = ? WHERE id = ?", (score, entry_id))


def get_entries_by_noise_score(category: str | None, min_score: float) -> list[dict]:
    """Le entry con punteggio di rumore (vedi set_noise_score) almeno
    `min_score`, qualunque sia la categoria o i tag che hanno: alimenta il
    pulsante "rumore di fondo" del frontend, la cui soglia e' regolabile.
    Le entry non ancora (ri)taggate con questo campo (noise_score NULL)
    contano come 0, quindi non compaiono mai finche' non viene retaggata."""
    with get_connection() as conn:
        query = "SELECT id, text FROM entries WHERE COALESCE(noise_score, 0) >= ?"
        params: list = [min_score]
        if category is not None:
            query += " AND category = ?"
            params.append(category)
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_entries_with_tags(category: str | None = None) -> list[dict]:
    """Tutte le entry con i loro tag. Per le citazioni tratte da un testo,
    `source` ne riporta titolo e autore; per i pensieri delle persone e' None.
    Con `category` filtra per 'stampante' | 'tesi' | 'interviste' | 'libro'."""
    with get_connection() as conn:
        query = (
            "SELECT e.id, e.text, e.likes, s.title AS source_title, s.author AS source_author "
            "FROM entries e LEFT JOIN sources s ON s.id = e.source_id"
        )
        params: tuple = ()
        if category is not None:
            query += " WHERE e.category = ?"
            params = (category,)
        entries = conn.execute(query, params).fetchall()

        tags_by_entry: dict[int, list[str]] = defaultdict(list)
        for row in conn.execute(
            "SELECT et.entry_id, t.name FROM entry_tags et JOIN tags t ON t.id = et.tag_id"
        ):
            tags_by_entry[row["entry_id"]].append(row["name"])

        return [
            {
                "id": entry["id"],
                "text": entry["text"],
                "likes": entry["likes"],
                "tags": tags_by_entry[entry["id"]],
                "source": (
                    {"title": entry["source_title"], "author": entry["source_author"]}
                    if entry["source_title"]
                    else None
                ),
            }
            for entry in entries
        ]


def get_tagged_entries(category: str | None = None) -> list[dict]:
    """Come get_entries_with_tags, ma solo le entry che hanno almeno un tag."""
    return [entry for entry in get_entries_with_tags(category) if entry["tags"]]


def get_entry_embeddings() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT entry_id, model, text_hash, vector FROM entry_embeddings"
        ).fetchall()


def upsert_entry_embeddings(rows: list[dict]) -> None:
    """Salva (o sostituisce) i vettori di similarita' delle entry."""
    if not rows:
        return
    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO entry_embeddings (entry_id, model, text_hash, vector)
            VALUES (:entry_id, :model, :text_hash, :vector)
            ON CONFLICT(entry_id) DO UPDATE SET
                model = excluded.model,
                text_hash = excluded.text_hash,
                vector = excluded.vector
            """,
            rows,
        )


# ── Testi letti dall'Oracolo ──

def get_source_by_file(file: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM sources WHERE file = ?", (file,)).fetchone()


def get_sources() -> list[sqlite3.Row]:
    """I testi caricati, con quanti passi e quante citazioni hanno dato."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT s.*,
                (SELECT COUNT(*) FROM passages p WHERE p.source_id = s.id) AS passages,
                (SELECT COUNT(*) FROM entries e WHERE e.source_id = s.id) AS fragments
            FROM sources s ORDER BY s.id
            """
        ).fetchall()


def replace_source(file: str, title: str, author: str, kind: str | None, file_hash: str) -> int:
    """Registra un testo, cancellando tutto cio' che una sua versione
    precedente aveva lasciato (passi, citazioni, tag e vettori collegati)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM sources WHERE file = ?", (file,))
        cursor = conn.execute(
            "INSERT INTO sources (file, title, author, kind, file_hash) VALUES (?, ?, ?, ?, ?)",
            (file, title, author, kind, file_hash),
        )
        return cursor.lastrowid


def finish_source(source_id: int, file_hash: str) -> None:
    """Segna un testo come letto fino in fondo. Finche' non succede la sua
    impronta resta vuota, e al prossimo giro viene riletto da capo: cosi' un
    caricamento interrotto a meta' non lascia testi monchi."""
    with get_connection() as conn:
        conn.execute("UPDATE sources SET file_hash = ? WHERE id = ?", (file_hash, source_id))


def delete_source(file: str) -> bool:
    """Toglie un testo (o, per una raccolta, tutte le sue interviste)."""
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM sources WHERE file = ? OR file LIKE ? || '#%'", (file, file)
        ).rowcount > 0


def insert_passages(source_id: int, rows: list[dict]) -> list[int]:
    """Salva i passi di un testo (testo + vettore), ritorna i loro id."""
    with get_connection() as conn:
        ids = []
        for position, row in enumerate(rows):
            cursor = conn.execute(
                "INSERT INTO passages (source_id, position, text, model, vector) VALUES (?, ?, ?, ?, ?)",
                (source_id, position, row["text"], row["model"], row["vector"]),
            )
            ids.append(cursor.lastrowid)
        return ids


def get_passages_signature() -> tuple[int, int]:
    """Quanti passi ci sono e l'id dell'ultimo: cambia quando cambia la biblioteca."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS last FROM passages"
        ).fetchone()
        return row["n"], row["last"]


def get_passages() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT p.id, p.text, p.model, p.vector, s.title, s.author, s.kind
            FROM passages p JOIN sources s ON s.id = p.source_id
            WHERE p.vector IS NOT NULL
            """
        ).fetchall()


_CATEGORY_BY_KIND = {"tesi": "tesi", "intervista": "interviste"}


def insert_fragments(source_id: int, rows: list[dict], kind: str | None = None) -> None:
    """Salva le citazioni di un testo come entry della nebulosa (ancora da
    taggare). Ogni riga: {"passage_id", "text"}. La categoria (per i 4
    pulsanti TUTTI/TESI/INTERVISTE/STAMPANTE del frontend) segue il `kind`
    del testo di provenienza; 'libro' per i testi senza kind tesi/intervista."""
    category = _CATEGORY_BY_KIND.get(kind, "libro")
    with get_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO entries (id, text, status, likes, source_id, category) "
            "VALUES (:id, :text, 'testo', 0, :source_id, :category)",
            [
                {
                    "id": FRAGMENT_ID_BASE + row["passage_id"],
                    "text": row["text"],
                    "source_id": source_id,
                    "category": category,
                }
                for row in rows
            ],
        )
