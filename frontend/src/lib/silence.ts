import type { TagEntry } from '@/lib/api';

// Il pensiero che una stella muta lascia al visitatore: preferibilmente uno
// che condivide qualche parola con la domanda, di una lunghezza che si legga
// d'un fiato; scelto sempre uguale per la stessa domanda e la stessa stella.
export function silentThought(entries: TagEntry[], question: string | null, tag: string): TagEntry | null {
  if (!entries.length) return null;
  const readable = entries.filter((e) => e.text.length >= 30 && e.text.length <= 260);
  const pool = readable.length ? readable : entries;
  const words = new Set(
    (question ?? '').toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 4)
  );
  const shared = (e: TagEntry) => e.text.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((w) => words.has(w)).length;
  const best = Math.max(0, ...pool.map(shared));
  const candidates = best > 0 ? pool.filter((e) => shared(e) === best) : pool;
  let seed = 0;
  for (const ch of `${question ?? ''}|${tag}`) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
  return candidates[seed % candidates.length];
}
