import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import type { OracleReading, OracleThought, TagDetail, TagEntry, TextSource } from '@/lib/api';
import { silentThought } from '@/lib/silence';

// Una domanda della cronologia, con la stella che le ha risposto.
export type AskedQuestion = { question: string; tag: string };

// Cosa dice l'Oracolo sulla stella aperta.
export type OracleState = {
  // stella a cui si riferisce
  tag: string;
  // domanda del visitatore a cui la stella risponde (null = nessuna: la
  // stella pronuncia una sentenza sul suo tema)
  question: string | null;
  // testo oracolare; null finche' l'Oracolo lo sta formulando
  text: string | null;
  // pensieri della nebulosa a cui si e' ispirato
  entries: OracleThought[];
  // frasi dei testi che ha consultato, citate con titolo e autore
  readings: OracleReading[];
  // l'Oracolo non e' raggiungibile: la stella tace e offre un pensiero che
  // ha ascoltato, citato alla lettera (vedi StarSilence)
  silent: boolean;
  // solo per un viaggio in silenzio: la stella e' stata scelta perche'
  // compare nelle parole della domanda (vero) o perche' e' tra le piu'
  // luminose (falso)
  near?: boolean;
};

// La stella senza l'Oracolo: non parla, ma lascia un pensiero che ha
// ascoltato, e si puo' provare a svegliarla.
function StarSilence({
  thought,
  question,
  near,
  onRetry,
}: {
  thought: TagEntry | null;
  question: string | null;
  near?: boolean;
  onRetry?: () => Promise<boolean>;
}) {
  const [state, setState] = useState<'idle' | 'trying' | 'asleep'>('idle');
  useEffect(() => {
    if (state !== 'asleep') return;
    const timer = window.setTimeout(() => setState('idle'), 4000);
    return () => window.clearTimeout(timer);
  }, [state]);

  const retry = async () => {
    if (!onRetry || state === 'trying') return;
    setState('trying');
    const awake = await onRetry().catch(() => false);
    // da sveglio la scheda passa da sola alla risposta: qui resta solo il caso muto
    if (!awake) setState('asleep');
  };

  const lead = question
    ? near
      ? "L'Oracolo dorme. La nebulosa ti ha portato alla stella più vicina alle tue parole: tace, ma ti lascia un pensiero che ha ascoltato."
      : "L'Oracolo dorme, e nessuna stella somiglia alle tue parole: la nebulosa ti ha portato da una delle più luminose. Tace, ma ti lascia un pensiero che ha ascoltato."
    : 'La stella tace, ma ti lascia un pensiero che ha ascoltato.';

  return (
    <>
      <p className="reply-silence">{lead}</p>
      {thought && (
        <blockquote className="reply-thought">
          <OracleText key={thought.id} text={thought.text} />
          <Attribution source={thought.source} />
          <Signature group={thought.group} />
        </blockquote>
      )}
      {onRetry && (
        <p className="reply-wake" aria-live="polite">
          <button onClick={retry} disabled={state === 'trying'}>
            {state === 'trying' ? 'la sto ascoltando…' : question ? 'riprova a chiederglielo' : 'riprova ad ascoltarla'}
          </button>
          {state === 'asleep' && <span>dorme ancora: riprova più tardi</span>}
        </p>
      )}
    </>
  );
}

// Da dove viene una citazione: autore e titolo del testo.
function Attribution({ source }: { source?: TextSource | null }) {
  if (!source) return null;
  return <cite className="reply-source">{source.author}, <em>{source.title}</em></cite>;
}

// Chi ha scritto un pensiero del Diario di bordo: solo il suo gruppo ("4° anno",
// "Docenti"), nella stessa firma delle citazioni.
function Signature({ group }: { group?: string | null }) {
  if (!group) return null;
  return <cite className="reply-source">{group}</cite>;
}

// Il testo dell'Oracolo compare una parola alla volta, come se lo stesse
// pronunciando in quel momento.
function OracleText({ text }: { text: string }) {
  const words = useMemo(() => text.split(/\s+/).filter(Boolean), [text]);
  const still = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const [said, setSaid] = useState(still ? words.length : 0);

  useEffect(() => {
    if (said >= words.length) return;
    const timer = window.setTimeout(() => setSaid(said + 1), said === 0 ? 500 : 130);
    return () => window.clearTimeout(timer);
  }, [said, words.length]);

  return (
    <p className="reply-answer" aria-label={text}>
      {words.map((word, i) => (
        // le parole non cambiano posizione: la chiave puo' essere l'indice
        <span key={i} className={i < said ? 'is-said' : undefined} aria-hidden="true">{word} </span>
      ))}
    </p>
  );
}

// Cronologia delle domande della visita, dalla prima all'ultima: si apre
// scorsa fino in fondo, dove ci sono le piu' recenti.
function QuestionHistory({
  history,
  current,
  onStep,
  hover,
}: {
  history: AskedQuestion[];
  current: number;
  onStep?: (index: number) => void;
  hover: (name: string) => object;
}) {
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [history.length]);

  return (
    <nav className="reply-trail" aria-label="Le tue domande">
      <ol ref={list}>
        {history.map((step, i) => (
          // la stessa domanda puo' tornare piu' volte: la chiave include la posizione
          <li key={`${i}-${step.question}`}>
            {i === current ? (
              <span className="reply-step is-current" aria-current="step">{step.question}</span>
            ) : (
              <button className="reply-step" onClick={() => onStep?.(i)} {...hover(step.tag)}>
                {step.question}
              </button>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

type Props = {
  tag: TagDetail | null;
  // Quante stelle collegate sono illuminate nella nebulosa (tutte, non solo
  // le 12 piu' rilevanti elencate qui sotto).
  linkedCount?: number;
  // Le domande fatte finora nella visita, con la stella che ha risposto.
  history?: AskedQuestion[];
  oracle?: OracleState | null;
  // Vero mentre la nebulosa porta il visitatore su questa stella: la
  // risposta aspetta l'arrivo.
  arriving?: boolean;
  onClose: () => void;
  onSelectTag: (name: string) => void;
  // Torna a una domanda della cronologia (indice in `history`).
  onHistoryStep?: (index: number) => void;
  // Passando il mouse su un tag, la sua stella si illumina.
  onHoverTag?: (name: string | null) => void;
  // Dopo la risposta: fare un'altra domanda, o viaggiare nella nebulosa.
  onAskAnother?: () => void;
  onWander?: () => void;
  // La figura del viaggio e' completa: si puo' guardarla subito.
  figureReady?: boolean;
  onRevealFigure?: () => void;
  // Prova a svegliare l'Oracolo per la stella aperta; risolve a vero se ora
  // risponde.
  onRetryOracle?: () => Promise<boolean>;
};

// Scheda del tag, ancorata a destra: a differenza del vecchio modale non ha
// sfondo scuro ne' blocca i click, cosi' la nebulosa resta navigabile.
export default function TagDetailPanel({
  tag,
  linkedCount,
  history = [],
  oracle,
  arriving = false,
  onClose,
  onSelectTag,
  onHistoryStep,
  onHoverTag,
  onAskAnother,
  onWander,
  figureReady = false,
  onRevealFigure,
  onRetryOracle,
}: Props) {
  // Quando arriva una nuova stella il fuoco entra nella scheda, sul titolo:
  // chi usa la tastiera continua da li' (Tab porta alle azioni e alle stelle
  // vicine) invece di restare sulla barra o perdersi nella pagina. Non si
  // ruba il fuoco a chi sta scrivendo nella barra.
  const title = useRef<HTMLHeadingElement>(null);
  const tagName = tag?.name;
  useEffect(() => {
    if (!tagName || arriving) return;
    if (document.activeElement instanceof HTMLInputElement) return;
    title.current?.focus({ preventScroll: true });
  }, [tagName, arriving]);

  if (!tag) return null;

  // L'Oracolo parla solo della stella mostrata (la scheda puo' essere ancora
  // quella precedente mentre la nuova si carica).
  const voice = oracle && oracle.tag === tag.name ? oracle : null;
  const silent = !!voice?.silent;
  // Il pensiero che la stella muta offre: non si ripete poi tra i frammenti.
  const offered = voice && silent && !arriving ? silentThought(tag.entries, voice.question, tag.name) : null;
  const fragments = offered ? tag.entries.filter((e) => e.id !== offered.id) : tag.entries;
  // La domanda a cui la stella risponde la rappresenta: diventa il titolo, e
  // il tag resta come piccola etichetta.
  const asked = oracle && oracle.tag === tag.name ? oracle.question : null;

  const hover = (name: string) => ({
    onMouseEnter: () => onHoverTag?.(name),
    onMouseLeave: () => onHoverTag?.(null),
    onFocus: () => onHoverTag?.(name),
    onBlur: () => onHoverTag?.(null),
  });
  // La domanda della cronologia a cui sta rispondendo questa stella (l'ultima volta).
  let current = -1;
  history.forEach((step, i) => {
    if (step.tag === tag.name && step.question === asked) current = i;
  });

  return (
    <aside className="reply-dock" aria-label={`Stella ${tag.name}`}>
      <button className="reply-close" onClick={onClose} aria-label="Chiudi la stella"><X size={18} aria-hidden="true" /></button>
      <div className="reply-scroll" key={tag.name}>
        {history.length > 1 && (
          <QuestionHistory history={history} current={current} onStep={onHistoryStep} hover={hover} />
        )}

        <h2 ref={title} tabIndex={-1} className={`reply-title${asked ? ' is-question' : ''}`}>{asked ?? tag.name}</h2>
        <p className="reply-meta">
          {asked && <strong>{tag.name}</strong>}
          <span>{tag.count} frammenti</span>
          <span>{linkedCount ?? tag.related.length} stelle collegate</span>
        </p>

        {voice && (
          <section className="reply-voice" aria-label="L'Oracolo">
            {arriving ? (
              <p className="reply-waiting">{silent ? 'la nebulosa ti porta tra le stelle…' : 'la stella sta per parlare…'}</p>
            ) : silent ? (
              <StarSilence
                thought={offered}
                question={voice.question}
                near={voice.near}
                onRetry={onRetryOracle}
              />
            ) : voice.text ? (
              <OracleText key={voice.text} text={voice.text} />
            ) : (
              <p className="reply-waiting">la stella sta per parlare…</p>
            )}
            {figureReady && (
              <button className="reply-figure" onClick={onRevealFigure}>la nebulosa ha preso forma: guardala</button>
            )}
            <div className="reply-actions">
              <button onClick={onAskAnother}>fai un'altra domanda</button>
              <button onClick={onWander}>viaggia nella nebulosa</button>
            </div>
            {voice.text && !arriving && voice.entries.length > 0 && (
              <div className="reply-section">
                <h3 className="reply-label">Pensieri che ha ascoltato</h3>
                {voice.entries.map((entry) => (
                  <p className="reply-heard" key={entry.id}>{entry.text}<Attribution source={entry.source} /><Signature group={entry.group} /></p>
                ))}
              </div>
            )}
            {voice.text && !arriving && voice.readings.length > 0 && (
              <div className="reply-section">
                <h3 className="reply-label">Dai testi che ha letto</h3>
                {voice.readings.map((reading) => (
                  <p className="reply-heard" key={`${reading.title}-${reading.text}`}>{reading.text}<Attribution source={reading} /></p>
                ))}
              </div>
            )}
          </section>
        )}

        {fragments.length > 0 && (
          <div className="reply-section">
            <h3 className="reply-label">Frammenti</h3>
            {fragments.map((entry) => (
              <p className={`reply-fragment${entry.source ? ' is-quote' : ''}`} key={entry.id}>
                {entry.text}
                <Attribution source={entry.source} />
                <Signature group={entry.group} />
              </p>
            ))}
          </div>
        )}

        {tag.related.length > 0 && (
          <div className="reply-section">
            <h3 className="reply-label">Stelle vicine</h3>
            <ul className="reply-bonds">
              {tag.related.map((rel) => {
                // La frase che contiene entrambi i tag: perche' sono collegati.
                const shared = rel.entries?.[0];
                const others = rel.weight - 1;
                return (
                  <li key={rel.name}>
                    <button className="reply-bond" onClick={() => onSelectTag(rel.name)} {...hover(rel.name)}>
                      <span className="reply-bond-name">{rel.name}<ArrowUpRight size={14} /></span>
                      {shared && <span className="reply-bond-quote">{shared.text}</span>}
                      {shared?.source && <Attribution source={shared.source} />}
                      <Signature group={shared?.group} />
                      {shared && others > 0 && (
                        <span className="reply-bond-more">
                          {others === 1 ? 'e un\'altra frase in comune' : `e altre ${others} frasi in comune`}
                        </span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </aside>
  );
}
