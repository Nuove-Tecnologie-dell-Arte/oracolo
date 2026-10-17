import { CircleHelp, Sparkles } from 'lucide-react';
import type { Category } from '@/lib/api';
import { CATEGORY_OPTIONS } from '@/categories';

// Intestazione della Nebulosa: marchio, numero di tag condivisi, lente di
// categoria, interruttore del rumore di fondo e i due pulsanti in alto a
// destra (domanda dell'Oracolo, presentazione).
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
      <div className="brand-lockup">
        <div>
          <p className="eyebrow">Oracolo</p>
          <h1>LA NEBULOSA</h1>
        </div>
      </div>
      <div className="header-center"><span className="status-dot" />Frammento <span className="header-divider" /> {tagCount} tag condivisi</div>
      <div className="header-actions">
        <div className="category-switch" role="group" aria-label="Filtra la nebulosa per categoria">
          {CATEGORY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`category-switch-btn${category === opt.value ? ' active' : ''}`}
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
        </div>
        <div className="noise-switch" role="group" aria-label="Rumore di fondo">
          <button
            type="button"
            className={`category-switch-btn noise-switch-btn${noiseVisible ? ' active' : ''}`}
            onClick={onToggleNoise}
            aria-pressed={noiseVisible}
            title="Messaggi che Ollama considera rumore di fondo, sopra la soglia qui a fianco"
          >
            Rumore di fondo
          </button>
          <button
            type="button"
            className="noise-threshold-btn"
            onClick={() => onAdjustNoiseThreshold(-0.1)}
            disabled={noiseThreshold <= 0}
            aria-label="Soglia piu' permissiva"
          >
            −
          </button>
          <span className="noise-threshold-value">{Math.round(noiseThreshold * 100)}%</span>
          <button
            type="button"
            className="noise-threshold-btn"
            onClick={() => onAdjustNoiseThreshold(0.1)}
            disabled={noiseThreshold >= 1}
            aria-label="Soglia piu' stringente"
          >
            +
          </button>
        </div>
        <a className="help-button" href={`${import.meta.env.BASE_URL}question.html`} aria-label="L'oracolo"><Sparkles size={16} strokeWidth={1.5} /></a>
        <button className="help-button" type="button" aria-label="Cos'è l'Oracolo" onClick={onShowAbout}><CircleHelp size={17} strokeWidth={1.5} /></button>
      </div>
    </header>
  );
}
