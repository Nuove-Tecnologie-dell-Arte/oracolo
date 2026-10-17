// Presentazione dell'Oracolo: si apre dal pulsante "?" in alto a destra.
export default function AboutOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div className="about-overlay" role="dialog" aria-label="Cos'è l'Oracolo" onClick={onClose}>
      <div className="loading-screen flex flex-col items-center justify-center text-center px-6">
        <div className="loading-orb" />
        <p className="max-w-2xl mt-6" style={{ fontSize: '13px', lineHeight: '1.6' }}>
          L'Oracolo è una mente collettiva open source che si dirama in mille frammenti incandescenti. È uno strumento, un archivio, un ambiente generativo, un agglomeratore di pensieri, testi, file, fonti e prende la forma di ciò da cui è composto. È una nebulosa mutaforma messa a disposizione del Viandante, che è uno stato d'animo: è il divergente, il ricercatore, l'esploratore; quello che si fa domande.
        </p>
        <p className="pt-12 text-sm text-[#F3C58B] animate-pulse">
          [ TORNA ALLA NEBULOSA ]
        </p>
      </div>
    </div>
  );
}
