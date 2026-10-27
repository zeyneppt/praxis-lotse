// Typen und Aufrufe gemäß API-Vertrag der Specs 004 und 005.

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// Antworten des LLM können dauern; danach gilt die Anfrage als gescheitert.
const ZEITLIMIT_MS = 90_000;

export type Kategorie = "normal" | "notfall" | "fehler";

export interface Quelle {
  dokument: string;
  titel: string;
}

export interface Slot {
  slot_id: string;
  standort_id: string;
  standort_name: string;
  fachrichtung: string;
  beginn: string;
}

export interface Aktion {
  typ: string;
  slots?: Slot[];
}

export interface ChatAntwort {
  sitzung_id: string;
  antwort: string;
  kategorie: Kategorie;
  quellen: Quelle[];
  aktion: Aktion | null;
  ki_hinweis: string;
}

export interface Anfrage {
  slot_id: string;
  name: string;
  geburtsdatum: string;
  telefon: string;
  einwilligung_datenschutz: boolean;
}

export interface AnfrageAntwort {
  anfrage_id: string;
  status: string;
  slot: Slot;
}

/** Der Server hat mit einem HTTP-Fehlerstatus geantwortet (im Gegensatz zu einem Netzwerkfehler). */
export class HttpFehler extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
  }
}

async function postJson<T>(pfad: string, body: unknown): Promise<T> {
  const antwort = await fetch(`${API_URL}${pfad}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(ZEITLIMIT_MS),
  });
  if (!antwort.ok) {
    throw new HttpFehler(antwort.status);
  }
  return (await antwort.json()) as T;
}

export function chatSenden(nachricht: string, sitzungId: string | null): Promise<ChatAntwort> {
  const body = sitzungId === null ? { nachricht } : { nachricht, sitzung_id: sitzungId };
  return postJson<ChatAntwort>("/api/chat", body);
}

export function terminAnfragen(anfrage: Anfrage): Promise<AnfrageAntwort> {
  return postJson<AnfrageAntwort>("/api/termine/anfragen", anfrage);
}

export function terminVorschlaege(aktion: Aktion | null): Slot[] {
  return aktion?.typ === "termin_vorschlag" ? (aktion.slots ?? []) : [];
}
