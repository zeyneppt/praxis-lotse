import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { HttpFehler, terminAnfragen, type AnfrageAntwort, type Slot } from "./api";
import { terminZeit } from "./format";

type Zustand =
  | { art: "auswahl" }
  | { art: "formular"; slot: Slot; fehler?: string }
  | { art: "bestaetigt"; antwort: AnfrageAntwort };

function heute(): string {
  const jetzt = new Date();
  const monat = String(jetzt.getMonth() + 1).padStart(2, "0");
  const tag = String(jetzt.getDate()).padStart(2, "0");
  return `${jetzt.getFullYear()}-${monat}-${tag}`;
}

function SlotText({ slot }: { slot: Slot }) {
  const { datum, uhrzeit } = terminZeit(slot.beginn);
  return (
    <>
      <span className="slot-datum">
        {datum}, {uhrzeit}
      </span>
      <span>
        {slot.standort_name} ({slot.fachrichtung})
      </span>
    </>
  );
}

/** Terminvorschläge einer Assistenten-Nachricht mit Anfrageformular. */
export function Terminwahl({ slots }: { slots: Slot[] }) {
  const [zustand, setZustand] = useState<Zustand>({ art: "auswahl" });

  if (zustand.art === "bestaetigt") {
    return <Bestaetigung antwort={zustand.antwort} />;
  }

  return (
    <div className="terminwahl">
      <p className="terminwahl-titel">Freie Termine – bitte auswählen:</p>
      <ul className="slots">
        {slots.map((slot) => (
          <li key={slot.slot_id}>
            <button
              type="button"
              className="slot"
              data-testid="termin-slot"
              aria-pressed={zustand.art === "formular" && zustand.slot.slot_id === slot.slot_id}
              onClick={() => setZustand({ art: "formular", slot })}
            >
              <SlotText slot={slot} />
            </button>
          </li>
        ))}
      </ul>
      {zustand.art === "formular" && (
        <TerminFormular
          key={zustand.slot.slot_id}
          slot={zustand.slot}
          fehler={zustand.fehler}
          onErfolg={(antwort) => setZustand({ art: "bestaetigt", antwort })}
          onFehler={(fehler) => setZustand({ art: "formular", slot: zustand.slot, fehler })}
          onAbbrechen={() => setZustand({ art: "auswahl" })}
        />
      )}
    </div>
  );
}

interface FormularProps {
  slot: Slot;
  fehler?: string;
  onErfolg: (antwort: AnfrageAntwort) => void;
  onFehler: (fehler: string) => void;
  onAbbrechen: () => void;
}

function TerminFormular({ slot, fehler, onErfolg, onFehler, onAbbrechen }: FormularProps) {
  // Personenbezogene Daten bleiben in diesem Zustand und gehen nur an /api/termine/anfragen.
  const [name, setName] = useState("");
  const [geburtsdatum, setGeburtsdatum] = useState("");
  const [telefon, setTelefon] = useState("");
  const [einwilligung, setEinwilligung] = useState(false);
  const [sendet, setSendet] = useState(false);
  const nameFeld = useRef<HTMLInputElement>(null);
  const id = useId();

  useEffect(() => {
    nameFeld.current?.focus();
  }, []);

  async function absenden(ereignis: FormEvent<HTMLFormElement>) {
    ereignis.preventDefault();
    setSendet(true);
    try {
      const antwort = await terminAnfragen({
        slot_id: slot.slot_id,
        name: name.trim(),
        geburtsdatum,
        telefon: telefon.trim(),
        einwilligung_datenschutz: einwilligung,
      });
      onErfolg(antwort);
    } catch (e) {
      setSendet(false);
      if (e instanceof HttpFehler && e.status === 409) {
        onFehler("Dieser Termin ist leider schon vergeben. Bitte wählen Sie einen anderen Termin.");
      } else if (e instanceof HttpFehler && e.status === 422) {
        onFehler("Bitte prüfen Sie Ihre Angaben (Name, Geburtsdatum, Telefonnummer, Einwilligung).");
      } else if (e instanceof HttpFehler && e.status === 429) {
        onFehler("Zu viele Anfragen. Bitte versuchen Sie es in einer Minute erneut.");
      } else {
        onFehler(
          "Die Anfrage konnte nicht gesendet werden. Bitte prüfen Sie Ihre Internetverbindung und versuchen Sie es erneut.",
        );
      }
    }
  }

  const { datum, uhrzeit } = terminZeit(slot.beginn);

  return (
    <form className="termin-formular" onSubmit={absenden} aria-labelledby={`${id}-titel`}>
      <h2 id={`${id}-titel`} className="formular-titel">
        Termin anfragen: {datum}, {uhrzeit}, {slot.standort_name}
      </h2>
      <label htmlFor={`${id}-name`}>Vor- und Nachname</label>
      <input
        id={`${id}-name`}
        ref={nameFeld}
        data-testid="termin-name"
        type="text"
        autoComplete="name"
        required
        minLength={2}
        maxLength={100}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <label htmlFor={`${id}-geburtsdatum`}>Geburtsdatum</label>
      <input
        id={`${id}-geburtsdatum`}
        data-testid="termin-geburtsdatum"
        type="date"
        autoComplete="bday"
        required
        max={heute()}
        value={geburtsdatum}
        onChange={(e) => setGeburtsdatum(e.target.value)}
      />
      <label htmlFor={`${id}-telefon`}>Telefonnummer für Rückfragen</label>
      <input
        id={`${id}-telefon`}
        data-testid="termin-telefon"
        type="tel"
        autoComplete="tel"
        required
        minLength={6}
        maxLength={30}
        pattern="[0-9 +\/\-]{6,30}"
        value={telefon}
        onChange={(e) => setTelefon(e.target.value)}
      />
      <div className="einwilligung">
        <input
          id={`${id}-einwilligung`}
          data-testid="termin-einwilligung"
          type="checkbox"
          required
          checked={einwilligung}
          onChange={(e) => setEinwilligung(e.target.checked)}
        />
        <label htmlFor={`${id}-einwilligung`}>
          Ich willige ein, dass meine Angaben zur Bearbeitung dieser Terminanfrage gespeichert
          werden. Sie werden nach spätestens 30 Tagen gelöscht.
        </label>
      </div>
      {fehler && (
        <p className="fehler" role="alert">
          {fehler}
        </p>
      )}
      <div className="formular-knoepfe">
        <button type="submit" data-testid="termin-absenden" disabled={sendet}>
          {sendet ? "Wird gesendet …" : "Termin anfragen"}
        </button>
        <button type="button" className="zweitrangig" onClick={onAbbrechen} disabled={sendet}>
          Abbrechen
        </button>
      </div>
    </form>
  );
}

function Bestaetigung({ antwort }: { antwort: AnfrageAntwort }) {
  const element = useRef<HTMLDivElement>(null);
  const { datum, uhrzeit } = terminZeit(antwort.slot.beginn);

  useEffect(() => {
    element.current?.focus();
  }, []);

  return (
    <div
      className="bestaetigung"
      data-testid="termin-bestaetigung"
      role="status"
      tabIndex={-1}
      ref={element}
    >
      <p>
        <strong>Ihre Terminanfrage wurde gesendet.</strong>
      </p>
      <p>
        {datum}, {uhrzeit}
        <br />
        {antwort.slot.standort_name} ({antwort.slot.fachrichtung})
      </p>
      <p>Die Praxis meldet sich bei Ihnen, um den Termin zu bestätigen.</p>
    </div>
  );
}
