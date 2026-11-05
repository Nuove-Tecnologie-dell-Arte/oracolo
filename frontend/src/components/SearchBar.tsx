import { ArrowUp, Sparkles } from 'lucide-react';
import { useEffect, useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react';

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
  // Risultati navigabili con le frecce (schema combobox): l'indice 0 e' la
  // domanda all'Oracolo, i successivi le stelle trovate; -1 = nessuno. Esc
  // chiude l'elenco finche' non si scrive di nuovo.
  const [active, setActive] = useState(-1);
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    setActive(-1);
    setClosed(false);
  }, [searchTerm]);

  useEffect(() => {
    if (active >= 0) document.getElementById(`search-option-${active}`)?.scrollIntoView({ block: 'nearest' });
  }, [active]);

  const term = searchTerm.trim();
  const open = resultsVisible && !busy && !!term && !closed;
  const options = open ? 1 + matches.length : 0;
  const optionId = (i: number) => `search-option-${i}`;

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape' && open) {
      event.preventDefault();
      setClosed(true);
      return;
    }
    if (!options) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      // si gira su -1 (la barra) .. options-1, ricominciando ai bordi
      const step = event.key === 'ArrowDown' ? 1 : -1;
      setActive((i) => ((i + 1 + step + options + 1) % (options + 1)) - 1);
      return;
    }
    // Invio su una stella evidenziata la apre; altrimenti la barra fa la domanda.
    if (event.key === 'Enter' && active > 0) {
      event.preventDefault();
      onSelectMatch(matches[active - 1]);
    }
  };

  return (
    <form
      className={`oracle-input-wrap${busy ? ' is-asking' : ''}${inviting ? ' is-inviting' : ''}`}
      onSubmit={onSubmit}
      role="search"
    >
      <div className="input-icon" aria-hidden="true"><Sparkles size={17} strokeWidth={1.5} /></div>
      <input
        ref={inputRef}
        value={searchTerm}
        disabled={busy}
        onChange={(event) => onSearchTermChange(event.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
        placeholder="Fai una domanda all'Oracolo, o cerca un tag"
        aria-label="Fai una domanda all'Oracolo o cerca una stella"
        aria-describedby="search-hint"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls="search-results"
        aria-activedescendant={open && active >= 0 ? optionId(active) : undefined}
        autoComplete="off"
      />
      <span id="search-hint" className="sr-only">
        Scrivi una domanda e premi Invio, oppure il nome di una stella e scegli con le frecce.
      </span>
      <button type="submit" className="ask-button" disabled={busy || !term} aria-label="Chiedi all'Oracolo">
        <ArrowUp size={18} strokeWidth={2} aria-hidden="true" />
      </button>
      {busy && (
        <span className="oracle-asking" aria-hidden="true">
          {traveling ? 'la nebulosa ti porta dalla tua stella…' : "l'Oracolo cerca tra le stelle…"}
        </span>
      )}
      {open && (
        <ul className="search-results" id="search-results" role="listbox" aria-label="Domanda e stelle trovate">
          <li role="presentation">
            <button
              type="button"
              id={optionId(0)}
              role="option"
              aria-selected={active === 0}
              tabIndex={-1}
              className={`search-ask${active === 0 ? ' is-active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onAsk(searchTerm)}
            >
              <span className="search-result-label">Chiedi all'Oracolo: «{term}»</span>
              <span className="search-result-count" aria-hidden="true">invio</span>
            </button>
          </li>
          {matches.map((node, i) => (
            <li key={node.id} role="presentation">
              <button
                type="button"
                id={optionId(i + 1)}
                role="option"
                aria-selected={active === i + 1}
                tabIndex={-1}
                className={active === i + 1 ? 'is-active' : undefined}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => onSelectMatch(node)}
              >
                <span className="search-result-label">{node.label}</span>
                <span className="search-result-count">
                  {node.count}
                  <span className="sr-only"> frammenti</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
