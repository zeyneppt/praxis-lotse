import { useEffect, useRef, useState, type FormEvent } from "react";
import { chatSenden, HttpFehler } from "./api";
import { Nachricht, type Eintrag } from "./Nachricht";

// Gleicher Text wie `ki_hinweis` der API; gilt bis zur ersten Antwort.
const KI_HINWEIS = "Sie sprechen mit einem KI-Assistenten. Er ersetzt keine ärztliche Beratung.";
const MAX_LAENGE = 1000;

function fehlerText(fehler: unknown): string {
  if (fehler instanceof HttpFehler && fehler.status === 429) {
    return "Zu viele Nachrichten in kurzer Zeit. Bitte warten Sie einen Moment und versuchen Sie es erneut.";
  }
  if (fehler instanceof HttpFehler) {
    return "Der Assistent ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut oder rufen Sie Ihre Praxis an.";
  }
  return "Keine Verbindung zum Assistenten. Bitte prüfen Sie Ihre Internetverbindung und versuchen Sie es erneut.";
}

export default function App() {
  const [eintraege, setEintraege] = useState<Eintrag[]>([]);
  const [eingabe, setEingabe] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  // Einzige Live-Region für Antworten: Screenreader lesen jede Antwort genau einmal vor.
  const [ansage, setAnsage] = useState("");
  const [kiHinweis, setKiHinweis] = useState(KI_HINWEIS);
  // Nur im Zustand der Seite, bewusst nicht in localStorage (Spec 008).
  const [sitzungId, setSitzungId] = useState<string | null>(null);
  const naechsteId = useRef(0);
  const ende = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ende.current?.scrollIntoView({ block: "end" });
  }, [eintraege, laedt, fehler]);

  async function senden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    const text = eingabe.trim();
    if (!text || laedt) {
      return;
    }
    setEintraege((alt) => [...alt, { id: naechsteId.current++, von: "person", text }]);
    setEingabe("");
    setFehler(null);
    setAnsage("");
    setLaedt(true);
    try {
      const antwort = await chatSenden(text, sitzungId);
      setSitzungId(antwort.sitzung_id);
      setKiHinweis(antwort.ki_hinweis || KI_HINWEIS);
      setEintraege((alt) => [...alt, { id: naechsteId.current++, von: "assistent", antwort }]);
      setAnsage(`${antwort.kategorie === "notfall" ? "Notfall" : "Praxis-Lotse"}: ${antwort.antwort}`);
    } catch (e) {
      setFehler(fehlerText(e));
    } finally {
      setLaedt(false);
    }
  }

  return (
    <div className="seite">
      <header className="kopf">
        <h1>Praxis-Lotse</h1>
        <p className="ki-hinweis" data-testid="ki-hinweis">
          <span aria-hidden="true">ℹ️ </span>
          {kiHinweis}
        </p>
      </header>

      <main className="chat">
        {eintraege.length === 0 && (
          <p className="begruessung">
            Willkommen beim MVZ Musterverbund Franken. Fragen Sie mich zu Standorten,
            Öffnungszeiten, Untersuchungen oder Terminen. Im Notfall rufen Sie bitte{" "}
            <a href="tel:112">112</a> an.
          </p>
        )}
        <ol className="verlauf" aria-label="Chatverlauf">
          {eintraege.map((eintrag) => (
            <Nachricht key={eintrag.id} eintrag={eintrag} />
          ))}
        </ol>
        {laedt && (
          <p className="laden" role="status">
            <span className="laden-punkte" aria-hidden="true" />
            Der Assistent antwortet …
          </p>
        )}
        {fehler && (
          <p className="fehler" role="alert">
            {fehler}
          </p>
        )}
        <div ref={ende} />
        <p className="unsichtbar" aria-live="polite">
          {ansage}
        </p>
      </main>

      <form className="eingabe" onSubmit={senden}>
        <input
          type="text"
          data-testid="chat-eingabe"
          aria-label="Ihre Nachricht an den Praxis-Lotsen"
          placeholder="Ihre Frage …"
          maxLength={MAX_LAENGE}
          autoComplete="off"
          value={eingabe}
          onChange={(e) => setEingabe(e.target.value)}
        />
        <button type="submit" data-testid="chat-senden" disabled={laedt}>
          Senden
        </button>
      </form>
    </div>
  );
}
