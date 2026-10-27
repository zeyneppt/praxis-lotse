// Reine Hilfsfunktionen für die Anzeige und Formularprüfung.

const ZEITZONE = "Europe/Berlin";

const DATUM = new Intl.DateTimeFormat("de-DE", {
  timeZone: ZEITZONE,
  weekday: "long",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const UHRZEIT = new Intl.DateTimeFormat("de-DE", {
  timeZone: ZEITZONE,
  hour: "2-digit",
  minute: "2-digit",
});

// en-CA formatiert als YYYY-MM-DD.
const ISO_DATUM = new Intl.DateTimeFormat("en-CA", {
  timeZone: ZEITZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Datum und Uhrzeit eines Termins (`beginn` als ISO 8601) in deutscher Ortszeit. */
export function terminZeit(beginn: string): { datum: string; uhrzeit: string } {
  const zeitpunkt = new Date(beginn);
  return { datum: DATUM.format(zeitpunkt), uhrzeit: `${UHRZEIT.format(zeitpunkt)} Uhr` };
}

/** Der Vortag von `jetzt` in Europe/Berlin als YYYY-MM-DD (spätestes gültiges Geburtsdatum, Spec 005). */
export function gesternInBerlin(jetzt: Date = new Date()): string {
  const heute = new Date(`${ISO_DATUM.format(jetzt)}T00:00:00Z`);
  heute.setUTCDate(heute.getUTCDate() - 1);
  return heute.toISOString().slice(0, 10);
}

// Wie der Server (Spec 005): nur Ziffern, Leerzeichen, +, -, /, davon mindestens 6 Ziffern.
// Für das HTML-Attribut `pattern` (wird ganz verankert und im v-Modus ausgewertet).
export const TELEFON_MUSTER = String.raw`[ +\/\-]*(?:[0-9][ +\/\-]*){6,}`;
export const MIN_TELEFON_ZIFFERN = 6;

export type TextTeil = { text: string; telefon?: string };

// Trenner innerhalb einer Nummer: Leerzeichen, Bindestrich ohne Leerzeichen, Schrägstrich.
// „08 - 12" (Bereich mit Leerzeichen) und Zeilenumbrüche trennen also Nummern.
const TRENNER = String.raw`(?: ?\/ ?|-| )`;

// Notruf 112, Bereitschaftsdienst 116117 sowie Nummern mit +49 oder einer Vorwahl
// aus 0 und mindestens zwei Ziffern (schließt „03/2026" oder „08-12" aus).
const TELEFONNUMMER = new RegExp(
  String.raw`(?<![\d+])(?:\+49${TRENNER}?\d+(?:${TRENNER}\d+)*|0\d{2,}(?:${TRENNER}\d+)*|116 ?117|112)(?!\d)`,
  "g",
);

function telefonZiel(nummer: string): string | null {
  const ziffern = nummer.replace(/[^\d+]/g, "");
  if (ziffern === "112" || ziffern === "116117") {
    return `tel:${ziffern}`;
  }
  // Nationale Schreibweise zählen: +49 911 … entspricht 0911 …
  const national = ziffern.startsWith("+49") ? `0${ziffern.slice(3)}` : ziffern;
  return national.length >= MIN_TELEFON_ZIFFERN ? `tel:${ziffern}` : null;
}

/** Zerlegt einen Text in normale Abschnitte und Telefonnummern mit `tel:`-Ziel. */
export function telefonnummernTrennen(text: string): TextTeil[] {
  const teile: TextTeil[] = [];
  let position = 0;
  for (const treffer of text.matchAll(TELEFONNUMMER)) {
    const ziel = telefonZiel(treffer[0]);
    if (ziel === null) {
      continue;
    }
    const start = treffer.index;
    if (start > position) {
      teile.push({ text: text.slice(position, start) });
    }
    teile.push({ text: treffer[0], telefon: ziel });
    position = start + treffer[0].length;
  }
  if (position < text.length) {
    teile.push({ text: text.slice(position) });
  }
  return teile;
}
