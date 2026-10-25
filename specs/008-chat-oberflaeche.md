# Spec 008 – Chat-Oberfläche

**Status:** offen
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

