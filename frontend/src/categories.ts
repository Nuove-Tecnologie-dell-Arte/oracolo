import type { Category } from '@/lib/api';

// Lente da cui guardare la nebulosa, scelta nell'header: cambiarla ricarica
// la pagina (il viaggio/figure in corso ripartono da capo con il nuovo
// insieme di stelle), persistita in ?category= cosi' il link resta condiviso.
export const CATEGORY_OPTIONS: { value: Category; label: string }[] = [
  { value: 'tutti', label: 'Tutti' },
  { value: 'tesi', label: 'Tesi' },
  { value: 'interviste', label: 'Interviste' },
  { value: 'stampante', label: 'Stampante' },
];

export function categoryFromUrl(): Category {
  const value = new URLSearchParams(window.location.search).get('category');
  return CATEGORY_OPTIONS.some((opt) => opt.value === value) ? (value as Category) : 'tutti';
}
