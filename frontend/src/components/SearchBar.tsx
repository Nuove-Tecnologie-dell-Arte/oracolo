import { Sparkles } from 'lucide-react';
import type { FormEvent, RefObject } from 'react';

// Una stella trovata dalla ricerca (sottoinsieme di GraphNode: solo cio' che
// la barra deve mostrare ed e' in grado di passare a onSelect).
export type SearchMatch = { id: string; label: string; count: number };

// Barra in basso: ricerca live dei tag mentre si scrive (nessun invio
// richiesto) e, sopra i risultati, la scorciatoia per fare la domanda
// all'Oracolo con lo stesso testo.
export default function SearchBar({
  inputRef,
  searchTerm,
  onSearchTermChange,
  busy,
  inviting,
  onFocus,
  resultsVisible,
  onBlur,
  onSubmit,
  traveling,
  matches,
  onAsk,
  onSelectMatch,
}: {
  inputRef: RefObject<HTMLInputElement>;
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  busy: boolean;
  inviting: boolean;
  onFocus: () => void;
  resultsVisible: boolean;
  onBlur: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  traveling: boolean;
  matches: SearchMatch[];
  onAsk: (question: string) => void;
  onSelectMatch: (match: SearchMatch) => void;
}) {
  return (
    <form
      className={`oracle-input-wrap${busy ? ' is-asking' : ''}${inviting ? ' is-inviting' : ''}`}
      onSubmit={onSubmit}
    >
      <div className="input-icon"><Sparkles size={17} strokeWidth={1.5} /></div>
      <input
        ref={inputRef}
        value={searchTerm}
        disabled={busy}
        onChange={(event) => onSearchTermChange(event.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
        placeholder="Fai una domanda all'Oracolo, o cerca un tag"
        aria-label="Fai una domanda all'Oracolo o cerca un tag"
      />
      {busy && (
        <span className="oracle-asking">
          {traveling ? 'la nebulosa ti porta dalla tua stella…' : "l'Oracolo cerca tra le stelle…"}
        </span>
      )}
      {resultsVisible && !busy && searchTerm.trim() && (
        <ul className="search-results">
          <li>
            <button type="button" className="search-ask" onMouseDown={(e) => e.preventDefault()} onClick={() => onAsk(searchTerm)}>
              <span className="search-result-label">Chiedi all'Oracolo: «{searchTerm.trim()}»</span>
              <span className="search-result-count">invio</span>
            </button>
          </li>
          {matches.map((node) => (
            <li key={node.id}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => onSelectMatch(node)}>
                <span className="search-result-label">{node.label}</span>
                <span className="search-result-count">{node.count}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
