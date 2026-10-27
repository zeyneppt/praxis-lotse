# Spec 008 – Chat-Oberfläche

**Status:** fertig
**Abhängigkeiten:** 004, 005, 006
**Abnahmetests:** `tests/acceptance/008_oberflaeche.robot` (Tag `spec-008`)

## Ziel

Eine schlichte, gut lesbare Weboberfläche, über die Patientinnen und Patienten
mit dem Assistenten sprechen, Quellen sehen und eine Terminanfrage stellen.
Sie muss auf dem Smartphone genauso gut funktionieren wie am Desktop.

## Anforderungen

1. Eine Seite unter `http://localhost:5173/` mit genau einem `<h1>` mit dem
   Text „Praxis-Lotse". Vor der ersten Frage gibt es keine Assistenten-Nachricht
   (keine Begrüßung als `nachricht-assistent`; eine Begrüßung darf als normaler Text erscheinen).
2. **KI-Hinweis** dauerhaft sichtbar oberhalb des Chats, Text aus `ki_hinweis`
   bzw. vor der ersten Antwort derselbe Text als Konstante.
3. **Chatverlauf:** Nachrichten der Person rechts, des Assistenten links.
   Unter jeder Assistenten-Nachricht mit Quellen eine Quellenliste mit den Titeln.
4. **Notfallantworten** (`kategorie: "notfall"`) werden deutlich hervorgehoben
   (roter Rahmen, Warnsymbol, Telefonnummern als `tel:`-Links).
5. **Terminvorschläge** (`aktion.typ == "termin_vorschlag"`): Termine als
   Schaltflächen mit Datum, Uhrzeit, Standort. Klick öffnet ein Formular mit
   Name, Geburtsdatum, Telefon und Einwilligungs-Checkbox. Das Formular sendet
   **direkt** an `POST /api/termine/anfragen`, nicht an den Chat.
   Nach Erfolg: Bestätigung mit Datum, Uhrzeit und Standort; bei `409`:
   Hinweis, dass der Termin vergeben ist.
6. **Bedienbarkeit:** Der Senden-Knopf hat sichtbaren Text (nicht nur ein Symbol). Enter sendet, Senden-Knopf während der Anfrage deaktiviert,
   Ladeanzeige, Fehlermeldung bei Netzwerkfehler. Mindestschriftgröße 16 px,
   Kontrast nach WCAG AA, alle Bedienelemente per Tastatur erreichbar und beschriftet.
7. Ab 375 px Breite ohne horizontales Scrollen nutzbar.
8. Die `sitzung_id` wird im Zustand der Seite gehalten (nicht in localStorage).

## Pflicht-Testattribute (`data-testid`)

Die Abnahmetests nutzen ausschließlich diese Attribute:

| Element | `data-testid` |
|---|---|
| KI-Hinweis | `ki-hinweis` |
| Eingabefeld | `chat-eingabe` |
| Senden-Knopf | `chat-senden` |
| jede Assistenten-Nachricht | `nachricht-assistent` |
| jede Nachricht der Person | `nachricht-person` |
| Quellenliste einer Nachricht | `quellen` |
| Notfall-Nachricht (zusätzlich zu `nachricht-assistent`, am selben Element als `data-kategorie="notfall"`) | – |
| Terminschaltfläche | `termin-slot` |
| Formularfelder | `termin-name`, `termin-geburtsdatum`, `termin-telefon`, `termin-einwilligung` |
| Absenden des Formulars | `termin-absenden` |
| Bestätigung | `termin-bestaetigung` |

## Nicht im Umfang

- Login, Mehrsprachigkeit, mobile App (siehe README „Nächste Schritte")

## Umsetzungsnotizen

Plan (2026-10-27):

1. `frontend/src/api.ts`: Typen aus dem API-Vertrag (`ChatAntwort`, `Slot`, `Anfrage`, `AnfrageAntwort`)
   und `fetch`-Aufrufe für `POST /api/chat` und `POST /api/termine/anfragen` (Basis `VITE_API_URL`).
2. `frontend/src/format.ts`: reine Funktionen – Termin in `Europe/Berlin` formatieren,
   Telefonnummern im Antworttext erkennen und in `tel:`-Links umwandeln.
3. `App.tsx`: Kopf mit `<h1>` und KI-Hinweis (Konstante, danach `ki_hinweis` der Antwort), Chatverlauf,
   Eingabeformular (Enter sendet, Knopf mit Text, während der Anfrage deaktiviert, Ladeanzeige,
   Fehlermeldung). `sitzung_id` nur im React-Zustand.
4. Nachrichten-Komponente: Person rechts, Assistent links, Quellenliste mit Titeln,
   Notfall mit `data-kategorie="notfall"`, rotem Rahmen, Warnsymbol und `tel:`-Links.
5. Terminvorschläge als Schaltflächen; Formular (Name, Geburtsdatum, Telefon, Einwilligung) sendet
   direkt an `/api/termine/anfragen`; Bestätigung bzw. Hinweis bei `409`. Personendaten nur im
   Formularzustand, kein Logging, nach Erfolg verworfen.
6. CSS: Mindestschrift 16 px, AA-Kontrast, sichtbarer Fokus, ab 375 px ohne horizontales Scrollen.
7. Keine Backend-Änderung → keine neuen pytest-Tests; Prüfung über Robot (`spec-008`), `make lint`.

Ergebnis (2026-10-27): `make lint` grün, `make test` 327/327 (keine Backend-Änderung),
`make acceptance SPEC=008` 6/6 im ersten Lauf, `make acceptance` 61/61 (inkl. Spec 001 im Browser).
Der `llm`-Test „Terminanfrage über das Formular" wurde auf Anweisung nicht ausgeführt (`LLM_PROVIDER=fake`);
der Formularablauf wurde stattdessen mit gemocktem `/api/chat` und echtem `/api/termine/anfragen`
im Browser geprüft (Bestätigung, `409`-Hinweis, 375 px ohne horizontales Scrollen).

Nachbesserung nach Review (2026-10-27): Telefon-Links nur für echte Nummern, Fokusfarbe ≥ 3:1, eine Live-Region,
Formularprüfung wie der Server, vergebener Slot nach `409` gesperrt; Unit-Tests für `format.ts` mit `node:test`
(`make test`). `make lint` grün, `make test` 327 + 7, `make acceptance` 61/61.
