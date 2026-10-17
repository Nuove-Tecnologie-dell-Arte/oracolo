#!/usr/bin/env bash
# Installa Oracolo "divinazione" come servizio di sistema sul lab, accanto al
# servizio "oracolo" del main (porta 8000), che non viene toccato.
#
#   cd ~/Projects/oracolo && git checkout main && bash scripts/installa-servizio.sh
#
# Crea una seconda copia di lavoro del branch (git worktree) perche' una cartella
# non puo' servire due branch, ci copia il DB e il .env, ne costruisce il
# frontend e installa due servizi: ollama-oracolo (porta 11500) e
# oracolo-divinazione (porta 8001). Chiede la password di sudo per systemd.
#
# Variabili: DEST (default ~/Projects/oracolo-divinazione), BRANCH (divinazione).

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DEST:-$HOME/Projects/oracolo-divinazione}"
BRANCH="${BRANCH:-divinazione}"
PYTHON="$SRC/.venv/bin/python"
UNITS="$SRC/scripts/systemd"
SERVIZI=(ollama-oracolo oracolo-divinazione)

passo() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
fallisci() { echo "ERRORE: $*" >&2; exit 1; }

passo "1/6 Controlli"
[ -x "$PYTHON" ] || fallisci "manca il venv: $PYTHON"
cd "$SRC"
[ "$(git branch --show-current)" = "main" ] || fallisci "questa cartella ($SRC) serve il servizio 'oracolo' del main: portala su main con 'git checkout main' (poi 'cd frontend && npm run build' per la sua build)."
git fetch origin "$BRANCH" 2>/dev/null || true
git rev-parse --verify -q "$BRANCH" >/dev/null || git branch "$BRANCH" "origin/$BRANCH"
porta_occupata() { ss -ltn "sport = :$1" | tail -n +2 | grep -q .; }
for coppia in "11500:ollama-oracolo" "8001:oracolo-divinazione"; do
    porta="${coppia%%:*}"; servizio="${coppia##*:}"
    if porta_occupata "$porta" && ! systemctl is-active -q "$servizio"; then
        fallisci "la porta $porta e' occupata da un processo lanciato a mano: fermalo (ss -ltnp | grep :$porta, poi kill <pid>)."
    fi
done

passo "2/6 Copia di lavoro di '$BRANCH' in $DEST"
if [ -d "$DEST/.git" ] || [ -f "$DEST/.git" ]; then
    echo "Gia' presente: la aggiorno."
    git -C "$DEST" pull --ff-only origin "$BRANCH"
else
    git worktree add "$DEST" "$BRANCH"
fi

passo "3/6 DB e configurazione"
mkdir -p "$DEST/data"
if [ -f "$DEST/data/local.db" ]; then
    echo "$DEST/data/local.db esiste gia': lo lascio com'e'."
else
    cp -p "$SRC/data/local.db" "$DEST/data/local.db"
    echo "Copiato il DB di $SRC (da qui in poi i due DB sono separati)."
fi
[ -f "$DEST/.env" ] || { cp -p "$SRC/.env" "$DEST/.env" && echo "Copiato .env"; }

passo "4/6 Build del frontend"
(cd "$DEST/frontend" && npm ci --no-audit --no-fund && npm run build)

passo "5/6 Installo i servizi (sudo)"
for nome in "${SERVIZI[@]}"; do
    sed -e "s|@UTENTE@|$(id -un)|g" -e "s|@HOME@|$HOME|g" -e "s|@DIR@|$DEST|g" -e "s|@PYTHON@|$PYTHON|g" \
        "$UNITS/$nome.service" | sudo tee "/etc/systemd/system/$nome.service" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVIZI[@]}"

passo "6/6 Verifica"
for _ in $(seq 1 20); do
    curl -fs -m3 localhost:8001/api/health >/dev/null 2>&1 && break
    sleep 1
done
systemctl --no-pager --lines=0 status "${SERVIZI[@]}" | grep -E "^(●|\s+Active)" || true
curl -s -m10 localhost:8001/api/health || echo "(il server non risponde ancora: journalctl -u oracolo-divinazione -n 30)"
echo
cat <<FINE

Fatto. Comandi utili:
  journalctl -u oracolo-divinazione -f          # log del server
  sudo systemctl restart oracolo-divinazione    # riavvio
Per aggiornare dopo un push:
  cd $DEST && git pull && (cd frontend && npm run build) && sudo systemctl restart oracolo-divinazione
FINE
