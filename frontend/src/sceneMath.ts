// Funzioni e costanti pure per la nebulosa 3D (colori, curve della camera,
// numeri stabili): nessuna dipendenza da React o dallo stato di App.

export type Vec3 = [number, number, number];

// Numero stabile tra 0 e 1 ricavato da un testo: da' a ogni stella una
// sfumatura e un ritmo suoi, uguali a ogni caricamento.
export function hash01(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return ((h >>> 0) % 100000) / 100000;
}

// Il colore dato, con una lieve sfumatura diversa per ogni stella: nessuna
// e' identica a un'altra (e il grafo da' a ognuna il suo materiale, cosi' lo
// scintillio di una non trascina le altre).
export function shaded(rgb: number[], id: string, alpha = 1): string {
  const [r, g, b] = rgb.map((v, channel) => {
    const shade = (hash01(`${id}:${channel}`) - 0.5) * 14;
    return Math.round(Math.min(255, Math.max(0, v + shade)));
  });
  return `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
}

// Colore delle stelle per importanza (0 = tag con una sola frase, 1 = il tag
// piu' usato): da fredde a calde. Le fredde hanno un colore diverso ma
// vivo, non spento: sono la maggior parte della nebulosa e devono contare
// anche loro.
const IMPORTANCE_STOPS: [number, [number, number, number]][] = [
  [0, [138, 126, 255]],
  [0.3, [190, 164, 255]],
  [0.55, [242, 216, 224]],
  [0.78, [255, 214, 150]],
  [1, [255, 176, 84]],
];
// Luminosita' delle stelle meno importanti rispetto alle piu' importanti:
// appena piu' tenui, quanto basta a dare profondita'.
const FAINTEST_STAR = 0.86;

export function importanceColor(importance: number, id: string): string {
  const t = Math.min(1, Math.max(0, importance));
  let i = 1;
  while (i < IMPORTANCE_STOPS.length - 1 && t > IMPORTANCE_STOPS[i][0]) i++;
  const [t0, c0] = IMPORTANCE_STOPS[i - 1];
  const [t1, c1] = IMPORTANCE_STOPS[i];
  const k = (t - t0) / (t1 - t0);
  return shaded(c0.map((v, channel) => v + (c1[channel] - v) * k), id, FAINTEST_STAR + (1 - FAINTEST_STAR) * t);
}

// Punto a frazione `u` (0-1) della curva morbida che passa per `points`
// (Catmull-Rom uniforme).
export function alongPath(points: Vec3[], u: number): Vec3 {
  const last = points.length - 1;
  const scaled = Math.min(0.999999, Math.max(0, u)) * last;
  const i = Math.floor(scaled);
  const t = scaled - i;
  const p0 = points[Math.max(0, i - 1)];
  const p1 = points[i];
  const p2 = points[i + 1];
  const p3 = points[Math.min(last, i + 2)];
  return [0, 1, 2].map((axis) => 0.5 * (
    2 * p1[axis]
    + (p2[axis] - p0[axis]) * t
    + (2 * p0[axis] - 5 * p1[axis] + 4 * p2[axis] - p3[axis]) * t * t
    + (3 * p1[axis] - p0[axis] - 3 * p2[axis] + p3[axis]) * t * t * t
  )) as Vec3;
}

// La stessa curva, ma con `u` = parte della lunghezza gia' percorsa: con
// alongPath ogni tratto dura uguale, corto o lungo che sia, e la camera
// cambierebbe velocita' di colpo a ogni stella.
export function evenPath(points: Vec3[], samples = 240): { at: (u: number) => Vec3; length: number } {
  const marks: Vec3[] = [];
  const lengths: number[] = [];
  for (let i = 0; i <= samples; i++) {
    const p = alongPath(points, i / samples);
    const q = marks[i - 1];
    lengths.push(q ? lengths[i - 1] + Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) : 0);
    marks.push(p);
  }
  const total = lengths[samples] || 1;
  const at = (u: number): Vec3 => {
    const goal = Math.min(1, Math.max(0, u)) * total;
    let lo = 0;
    let hi = samples;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (lengths[mid] <= goal) lo = mid; else hi = mid;
    }
    const k = (goal - lengths[lo]) / (lengths[hi] - lengths[lo] || 1);
    const a = marks[lo];
    const b = marks[hi];
    return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
  };
  return { at, length: lengths[samples] };
}

// Chi ha chiesto al sistema meno animazioni salta i movimenti di camera.
export function reducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

// Distanza di un punto davanti alla camera (negativa se e' dietro), data la
// matrice `matrixWorldInverse.elements` della camera.
export function depthAhead(m: number[], x: number, y: number, z: number): number {
  return -(m[2] * x + m[6] * y + m[10] * z + m[14]);
}

// Da 0 a 1 partendo e arrivando con dolcezza (accelerazione nulla agli estremi).
export function smoother(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x * x * x * (x * (6 * x - 15) + 10);
}

type LinkEndpoints = {
  source: string | { id: string };
  target: string | { id: string };
};

export const endpoints = (link: LinkEndpoints): [string, string] => [
  typeof link.source === 'string' ? link.source : link.source.id,
  typeof link.target === 'string' ? link.target : link.target.id,
];

// Chiave di un collegamento, uguale nei due versi.
export const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`);
