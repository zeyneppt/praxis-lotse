import { terminVorschlaege, type ChatAntwort } from "./api";
import { telefonnummernTrennen } from "./format";
import { Terminwahl } from "./Terminwahl";

export type Eintrag =
  | { id: number; von: "person"; text: string }
  | { id: number; von: "assistent"; antwort: ChatAntwort };

function TextMitTelefon({ text }: { text: string }) {
  return (
    <p className="nachricht-text">
      {telefonnummernTrennen(text).map((teil, index) =>
        teil.telefon ? (
          <a key={index} href={teil.telefon}>
            {teil.text}
          </a>
        ) : (
          <span key={index}>{teil.text}</span>
        ),
      )}
    </p>
  );
}

export function Nachricht({ eintrag }: { eintrag: Eintrag }) {
  if (eintrag.von === "person") {
    return (
      <li className="zeile zeile-person">
        <div className="nachricht nachricht-person" data-testid="nachricht-person">
          <span className="unsichtbar">Sie: </span>
          <p className="nachricht-text">{eintrag.text}</p>
        </div>
      </li>
    );
  }

  const { antwort } = eintrag;
  const notfall = antwort.kategorie === "notfall";
  const slots = terminVorschlaege(antwort.aktion);

  return (
    <li className="zeile zeile-assistent">
      <div
        className={`nachricht nachricht-assistent${notfall ? " notfall" : ""}`}
        data-testid="nachricht-assistent"
        data-kategorie={antwort.kategorie}
        role={notfall ? "alert" : undefined}
      >
        {notfall ? (
          <p className="notfall-titel">
            <span aria-hidden="true">⚠️ </span>Notfall
          </p>
        ) : (
          <span className="unsichtbar">Praxis-Lotse: </span>
        )}
        <TextMitTelefon text={antwort.antwort} />
        {antwort.quellen.length > 0 && (
          <div className="quellen" data-testid="quellen">
            <p className="quellen-titel">Quellen:</p>
            <ul>
              {antwort.quellen.map((quelle) => (
                <li key={quelle.dokument}>{quelle.titel}</li>
              ))}
            </ul>
          </div>
        )}
        {slots.length > 0 && <Terminwahl slots={slots} />}
      </div>
    </li>
  );
}
