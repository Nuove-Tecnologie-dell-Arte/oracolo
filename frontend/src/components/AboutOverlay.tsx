import { useEffect, useRef } from 'react';

// Presentazione dell'Oracolo: si apre dal pulsante "?" in alto a destra. E'
// un dialogo vero: il fuoco entra sul pulsante per tornare alla nebulosa, ci
// resta finche' e' aperto (Tab non scivola nella pagina dietro) e all'uscita
// torna dove era. Esc lo chiude (vedi il gestore dei tasti in App).
export default function AboutOverlay({ onClose }: { onClose: () => void }) {
  const back = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    back.current?.focus();
    return () => before?.focus();
  }, []);

  return (
    <div
      className="about-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="about-title"
      aria-describedby="about-text"
      onClick={onClose}
      onKeyDown={(event) => {
        // l'unico elemento attivo e' il pulsante: Tab resta su di lui
        if (event.key === 'Tab') event.preventDefault();
      }}
    >
      <div className="loading-screen flex flex-col items-center justify-center text-center px-6">
        <div className="loading-orb" aria-hidden="true" />
        <h2 id="about-title" className="sr-only">Cos'è l'Oracolo</h2>
        <p id="about-text" className="max-w-2xl mt-6" style={{ fontSize: '13px', lineHeight: '1.6' }}>
          L'Oracolo è una mente collettiva open source che si dirama in mille frammenti incandescenti. È uno strumento, un archivio, un ambiente generativo, un agglomeratore di pensieri, testi, file, fonti e prende la forma di ciò da cui è composto. È una nebulosa mutaforma messa a disposizione del Viandante, che è uno stato d'animo: è il divergente, il ricercatore, l'esploratore; quello che si fa domande.
        </p>
        <button ref={back} type="button" className="about-back mt-9 animate-pulse" onClick={onClose}>
          [ TORNA ALLA NEBULOSA ]
        </button>
      </div>
    </div>
  );
}
