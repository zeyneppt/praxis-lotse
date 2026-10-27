// Reine Hilfsfunktionen für die Anzeige.

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

/** Datum und Uhrzeit eines Termins (`beginn` als ISO 8601) in deutscher Ortszeit. */
export function terminZeit(beginn: string): { datum: string; uhrzeit: string } {
  const zeitpunkt = new Date(beginn);
  return { datum: DATUM.format(zeitpunkt), uhrzeit: `${UHRZEIT.format(zeitpunkt)} Uhr` };
}

export type TextTeil = { text: string; telefon?: string };

// Notruf 112, Bereitschaftsdienst 116117 sowie Nummern mit Vorwahl (0… oder +49…).
const TELEFONNUMMER = /(?<![\d+])(?:\+49[\d /-]{6,}\d|0\d[\d /-]{4,}\d|116 ?117|112)(?!\d)/g;

/** Zerlegt einen Text in normale Abschnitte und Telefonnummern mit `tel:`-Ziel. */
export function telefonnummernTrennen(text: string): TextTeil[] {
  const teile: TextTeil[] = [];
  let position = 0;
  for (const treffer of text.matchAll(TELEFONNUMMER)) {
    const start = treffer.index;
    if (start > position) {
      teile.push({ text: text.slice(position, start) });
    }
    const nummer = treffer[0];
    teile.push({ text: nummer, telefon: `tel:${nummer.replace(/[^\d+]/g, "")}` });
    position = start + nummer.length;
  }
  if (position < text.length) {
    teile.push({ text: text.slice(position) });
  }
  return teile;
}
