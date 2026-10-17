#!/usr/bin/env bash
# Ritagga tutte le entry con i tag oracolari (le 64 situazioni) usando un
# Ollama temporaneo con qwen3.5-9b, poi ricalcola gli embedding con l'Ollama
# di sistema. Da lanciare sul lab, dalla radice del progetto o da qui:
#
#   bash scripts/tagga-oracolare.sh
#
# Fa tutto da solo: backup del DB, accensione e spegnimento dell'Ollama
# temporaneo (anche con Ctrl+C), riepilogo finale. Non tocca il servizio di
# sistema "ollama" e non riavvia `serve`.
#
# Variabili (con il loro default):
#   MODELLO_TAG=qwen3.5-9b           modello generativo dei tag
#   MODELLI_DIR=~/models/ollama      dove l'Ollama temporaneo cerca i modelli
#   PORTA_TEMP=11500                 porta dell'Ollama temporaneo
#   OLLAMA_SISTEMA=http://127.0.0.1:11434   Ollama di sistema, per gli embedding

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

MODELLO_TAG="${MODELLO_TAG:-qwen3.5-9b}"
MODELLI_DIR="${MODELLI_DIR:-$HOME/models/ollama}"
PORTA_TEMP="${PORTA_TEMP:-11500}"
OLLAMA_SISTEMA="${OLLAMA_SISTEMA:-http://127.0.0.1:11434}"
TEMP_URL="http://127.0.0.1:${PORTA_TEMP}"

PYTHON=python3
[ -x .venv/bin/python ] && PYTHON=.venv/bin/python

DB="$($PYTHON -c 'from backend import config; print(config.LOCAL_DB_PATH)')"
LOG_TEMP="$(mktemp -t ollama-temp.XXXXXX.log)"
OLLAMA_PID=""

passo() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

spegni_temporaneo() {
    if [ -n "$OLLAMA_PID" ] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
        kill "$OLLAMA_PID" 2>/dev/null || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
    OLLAMA_PID=""
}

pulizia() {
    local codice=$?
    spegni_temporaneo
    if [ "$codice" -ne 0 ] && [ -s "$LOG_TEMP" ]; then
        echo "--- ultime righe del log dell'Ollama temporaneo ---" >&2
        tail -n 15 "$LOG_TEMP" >&2
    fi
    rm -f "$LOG_TEMP"
    [ "$codice" -eq 0 ] || echo "Interrotto (codice $codice): Ollama temporaneo spento." >&2
}
trap pulizia EXIT
trap 'exit 130' INT TERM

attendi() {  # attendi <url> : aspetta che Ollama risponda (max 60 s)
    for _ in $(seq 1 60); do
        curl -fs -m2 "$1/api/tags" >/dev/null 2>&1 && return 0
        sleep 1
    done
    echo "Ollama non risponde su $1" >&2
    return 1
}

ha_modello() {  # ha_modello <url> <nome> : il modello e' presente?
    local elenco
    elenco="$(curl -fs -m5 "$1/api/tags")" || return 1
    grep -q "\"name\":\"$2[:\"]" <<<"$elenco"
}

passo "1/5 Backup del DB"
[ -f "$DB" ] || { echo "DB non trovato: $DB" >&2; exit 1; }
BACKUP="${DB%.db}.backup-$(date +%Y%m%d-%H%M%S).db"
cp -p "$DB" "$BACKUP"
echo "Copia in $BACKUP"

passo "2/5 Controllo Ollama di sistema (embedding)"
attendi "$OLLAMA_SISTEMA"
ha_modello "$OLLAMA_SISTEMA" bge-m3 || { echo "bge-m3 manca su $OLLAMA_SISTEMA" >&2; exit 1; }
echo "bge-m3 presente su $OLLAMA_SISTEMA"

passo "3/5 Accendo l'Ollama temporaneo ($TEMP_URL, modelli in $MODELLI_DIR)"
curl -fs -m2 "$TEMP_URL/api/tags" >/dev/null 2>&1 && { echo "La porta $PORTA_TEMP e' gia' occupata" >&2; exit 1; }
OLLAMA_HOST="127.0.0.1:${PORTA_TEMP}" OLLAMA_MODELS="$MODELLI_DIR" ollama serve >"$LOG_TEMP" 2>&1 &
OLLAMA_PID=$!
attendi "$TEMP_URL"
ha_modello "$TEMP_URL" "$MODELLO_TAG" || { echo "$MODELLO_TAG manca in $MODELLI_DIR" >&2; exit 1; }
echo "$MODELLO_TAG presente"

passo "4/5 Tagging oracolare di tutte le entry (puo' richiedere decine di minuti)"
# Il primo pensiero carica il modello sulla GPU: timeout largo. Le variabili
# nell'ambiente hanno la precedenza sul .env.
export TAG_MODE=oracolare OLLAMA_TAG_MODEL="$MODELLO_TAG" OLLAMA_HOST="$TEMP_URL"
export OLLAMA_TIMEOUT_SECONDS=180 OLLAMA_THINK=false
$PYTHON -m backend.main tag --retag
echo "Secondo giro, per le entry che avessero dato errore:"
$PYTHON -m backend.main tag
spegni_temporaneo
echo "Ollama temporaneo spento."

passo "5/5 Embedding con l'Ollama di sistema"
OLLAMA_HOST="$OLLAMA_SISTEMA" $PYTHON -m backend.main embed

passo "Riepilogo"
$PYTHON - "$DB" <<'EOF'
import sqlite3, sys

conn = sqlite3.connect(sys.argv[1])
totale = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
ancora = conn.execute("SELECT COUNT(*) FROM entries WHERE tagged_at IS NULL").fetchone()[0]
righe = conn.execute(
    """SELECT t.name, COUNT(*) AS n FROM entry_tags et JOIN tags t ON t.id = et.tag_id
       GROUP BY t.id ORDER BY n DESC"""
).fetchall()
print(f"Entry: {totale} (senza tag: {ancora}). Tag distinti: {len(righe)} (massimo 64 + 'rumore di fondo').")
print("Le 10 piu' frequenti (quota delle entry che le hanno):")
for nome, n in righe[:10]:
    print(f"  {nome:<20} {n:>5}  {100 * n / totale:5.1f}%")
ricettivo = dict(righe).get("ricettivo", 0)
print(f"\nBias del Ricettivo: {ricettivo} entry su {totale} ({100 * ricettivo / totale:.1f}%).")
print("Letture salvate:", conn.execute("SELECT COUNT(*) FROM entries WHERE reading IS NOT NULL").fetchone()[0])
EOF

echo
echo "Fatto. Per vedere il risultato riavvia 'serve' (il processo in corso ha il codice vecchio)."
