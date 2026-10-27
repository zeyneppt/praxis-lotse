import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { HttpFehler, terminAnfragen, type AnfrageAntwort, type Slot } from "./api";
import { gesternInBerlin, TELEFON_MUSTER, terminZeit } from "./format";

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
  const [gewaehlt, setGewaehlt] = useState<Slot | null>(null);
  const [fehler, setFehler] = useState<string>();
  // Slots, für die der Server 409 gemeldet hat; sie sind nicht mehr wählbar.
  const [vergeben, setVergeben] = useState<ReadonlySet<string>>(new Set());
  const [bestaetigt, setBestaetigt] = useState<AnfrageAntwort | null>(null);

  if (bestaetigt) {
    return <Bestaetigung antwort={bestaetigt} />;
  }

  function waehlen(slot: Slot | null) {
    setGewaehlt(slot);
    setFehler(undefined);
  }

  function alsVergebenMarkieren(slotId: string) {
    setVergeben((alt) => new Set(alt).add(slotId));
    setFehler("Dieser Termin ist leider schon vergeben. Bitte wählen Sie einen anderen Termin.");
  }

  return (
    <div className="terminwahl">
      <p className="terminwahl-titel">Freie Termine – bitte auswählen:</p>
      <ul className="slots">
        {slots.map((slot) => {
          const istVergeben = vergeben.has(slot.slot_id);
          return (
            <li key={slot.slot_id}>
              <button
                type="button"
                className="slot"
                data-testid="termin-slot"
                disabled={istVergeben}
                aria-pressed={gewaehlt?.slot_id === slot.slot_id}
                onClick={() => waehlen(slot)}
              >
                <SlotText slot={slot} />
                {istVergeben && <span className="slot-vergeben">Bereits vergeben</span>}
              </button>
            </li>
          );
        })}
      </ul>
      {gewaehlt && (
        // Ohne `key`: Beim Wechsel des Termins bleiben die eingegebenen Daten erhalten.
        <TerminFormular
          slot={gewaehlt}
          vergeben={vergeben.has(gewaehlt.slot_id)}
          fehler={fehler}
          onErfolg={setBestaetigt}
          onVergeben={alsVergebenMarkieren}
          onFehler={setFehler}
          onAbbrechen={() => waehlen(null)}
        />
      )}
    </div>
  );
}

interface FormularProps {
  slot: Slot;
  vergeben: boolean;
  fehler?: string;
  onErfolg: (antwort: AnfrageAntwort) => void;
  onVergeben: (slotId: string) => void;
  onFehler: (fehler: string) => void;
  onAbbrechen: () => void;
}

function TerminFormular({
  slot,
  vergeben,
  fehler,
  onErfolg,
  onVergeben,
  onFehler,
  onAbbrechen,
}: FormularProps) {
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
        onVergeben(slot.slot_id);
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
        max={gesternInBerlin()}
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
        pattern={TELEFON_MUSTER}
        title="Mindestens 6 Ziffern; erlaubt sind Ziffern, Leerzeichen, +, - und /"
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
        <button type="submit" data-testid="termin-absenden" disabled={sendet || vergeben}>
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
