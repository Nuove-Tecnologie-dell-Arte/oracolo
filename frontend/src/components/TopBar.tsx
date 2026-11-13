import { CircleHelp, Sparkles } from 'lucide-react';
import type { Category } from '@/lib/api';
import { CATEGORY_OPTIONS } from '@/categories';

// Intestazione della Nebulosa: marchio e numero di tag a sinistra, categorie
// al centro, a destra rumore di fondo (con soglia, visibile solo se attivo) e
// i due pulsanti (domanda dell'Oracolo, presentazione).
export default function TopBar({
  tagCount,
  category,
  noiseVisible,
  noiseThreshold,
  onToggleNoise,
  onAdjustNoiseThreshold,
  onShowAbout,
}: {
  tagCount: number;
  category: Category;
  noiseVisible: boolean;
  noiseThreshold: number;
  onToggleNoise: () => void;
  onAdjustNoiseThreshold: (delta: number) => void;
  onShowAbout: () => void;
}) {
  return (
    <header className="topbar">
      <div className="brand">
        <h1 className="brand-name">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 0c.6 6.6 4.8 11.4 12 12-7.2.6-11.4 5.4-12 12-.6-6.6-4.8-11.4-12-12C7.2 11.4 11.4 6.6 12 0Z" /></svg>
          La Nebulosa
        </h1>
        <p className="brand-count"><span className="status-dot" />{tagCount} tag condivisi</p>
      </div>
      <nav className="category-tabs" aria-label="Filtra la nebulosa per categoria">
        {CATEGORY_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`category-tab${category === opt.value ? ' active' : ''}`}
            aria-current={category === opt.value ? 'page' : undefined}
            onClick={() => {
              if (opt.value === category) return;
              const url = new URL(window.location.href);
              if (opt.value === 'tutti') url.searchParams.delete('category');
              else url.searchParams.set('category', opt.value);
              window.location.href = url.toString();
            }}
          >
            {opt.label}
          </button>
        ))}
      </nav>
      <div className="topbar-tools">
        {noiseVisible && (
          <div className="noise-stepper" role="group" aria-label="Soglia del rumore di fondo">
            <button
              type="button"
              className="noise-step"
              onClick={() => onAdjustNoiseThreshold(-0.1)}
              disabled={noiseThreshold <= 0}
              aria-label="Soglia piu' permissiva"
            >
              −
            </button>
            <span className="noise-value">{Math.round(noiseThreshold * 100)}%</span>
            <button
              type="button"
              className="noise-step"
              onClick={() => onAdjustNoiseThreshold(0.1)}
              disabled={noiseThreshold >= 1}
              aria-label="Soglia piu' stringente"
            >
              +
            </button>
          </div>
        )}
        <button
          type="button"
          className={`noise-toggle${noiseVisible ? ' active' : ''}`}
          onClick={onToggleNoise}
          aria-pressed={noiseVisible}
          aria-label="Rumore di fondo"
          title="Messaggi che Ollama considera rumore di fondo, sopra la soglia indicata"
        >
          <span>Rumore di fondo</span>
        </button>
        <a className="tool-button" href={`${import.meta.env.BASE_URL}question.html`} aria-label="L'oracolo"><Sparkles size={17} strokeWidth={1.5} /></a>
        <button className="tool-button" type="button" aria-label="Cos'è l'Oracolo" onClick={onShowAbout}><CircleHelp size={18} strokeWidth={1.5} /></button>
      </div>
    </header>
  );
}
