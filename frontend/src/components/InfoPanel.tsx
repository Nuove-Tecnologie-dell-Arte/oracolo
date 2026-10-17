// Pannello informativo a sinistra: titolo, una breve spiegazione e la legenda
// di come leggere la nebulosa. Si fa da parte durante il viaggio e mentre una
// stella e' aperta, coprirebbe le stelle collegate.
export default function InfoPanel({
  tagCount,
  linkCount,
  receded,
}: {
  tagCount: number;
  linkCount: number;
  receded: boolean;
}) {
  return (
    <aside className={`side-panel left-panel${receded ? ' is-receded' : ''}`}>
      <p className="field-title">Un archivio di <em>memorie collettive.</em></p>
      <p className="field-copy">Ogni tag nasce da un pensiero condiviso e si lega agli altri che ne condividono il tema. Esplora la nebulosa per scoprire come si intrecciano.</p>
      <ul className="field-legend" aria-label="Come leggere la nebulosa">
        <li>
          <svg width="30" height="16" viewBox="0 0 30 16" aria-hidden="true">
            <circle cx="8" cy="8" r="6" fill="currentColor" />
            <circle cx="24" cy="8" r="2.5" fill="currentColor" />
          </svg>
          Più grande, più pensieri
        </li>
        <li>
          <svg width="30" height="16" viewBox="0 0 30 16" aria-hidden="true">
            <line x1="5" y1="8" x2="25" y2="8" stroke="currentColor" strokeWidth="1" />
            <circle cx="5" cy="8" r="3" fill="currentColor" />
            <circle cx="25" cy="8" r="3" fill="currentColor" />
          </svg>
          Un filo: pensieri in comune
        </li>
      </ul>
      <p className="field-tally">{tagCount} tag, {linkCount} connessioni</p>
    </aside>
  );
}
