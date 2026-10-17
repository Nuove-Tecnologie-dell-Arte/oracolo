// Pannello informativo a sinistra: si fa da parte durante il viaggio e
// mentre una stella e' aperta, coprirebbe le stelle collegate.
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
      <p className="field-title">Un archivio di <br /><em>memorie collettive.</em></p>
      <p className="field-copy">Ogni tag nasce da un pensiero condiviso e si lega agli altri che ne condividono il tema. Esplora la nebulosa per scoprire come si intrecciano.</p>
      <div className="rule" />
      <div className="metric-grid">
        <div><strong>{tagCount}</strong><span>tag</span></div>
        <div><strong>{linkCount}</strong><span>connessioni</span></div>
      </div>
    </aside>
  );
}
