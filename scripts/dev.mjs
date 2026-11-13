// `npm run dev`: avvia backend (`backend.main serve`) e dev server Vite insieme.
// Se il backend e' gia' attivo sulla porta (es. in tmux) lo riusa senza avviarne un altro.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import net from 'node:net';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const porta = Number(process.env.SERVE_PORT ?? 8000);
const venvPython = `${root}/.venv/bin/python`;
const python = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : 'python3');

const figli = [];
const avvia = (nome, cmd, args, opzioni) => {
  const figlio = spawn(cmd, args, { stdio: 'inherit', ...opzioni });
  figlio.on('exit', (codice) => {
    console.log(`[dev] ${nome} terminato (${codice})`);
    chiudi(codice ?? 0);
  });
  figli.push(figlio);
};

let chiuso = false;
const chiudi = (codice) => {
  if (chiuso) return;
  chiuso = true;
  figli.forEach((f) => f.kill('SIGTERM'));
  process.exit(codice);
};
process.on('SIGINT', () => chiudi(0));
process.on('SIGTERM', () => chiudi(0));

const portaOccupata = await new Promise((resolve) => {
  const s = net.connect(porta, '127.0.0.1');
  s.on('connect', () => (s.destroy(), resolve(true)));
  s.on('error', () => resolve(false));
});

if (portaOccupata) {
  console.log(`[dev] backend gia' attivo su :${porta}, lo riuso`);
} else {
  avvia('backend', python, ['-m', 'backend.main', 'serve'], { cwd: root });
}
avvia('frontend', 'npm', ['--prefix', 'frontend', 'run', 'dev'], { cwd: root });
