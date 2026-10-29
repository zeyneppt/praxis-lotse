# Spec 009 – Terminwunsch regelbasiert erkennen

**Status:** offen
**Abhängigkeiten:** 005, 006, 008
**Abnahmetests:** `tests/acceptance/009_terminwunsch.robot` und
`tests/acceptance/009_terminwunsch_ui.robot` (Tag `spec-009`)

## Ziel

Bei der Generalprobe mit `qwen2.5:7b` (29.10.2026) hat das Modell bei
„Ich hätte gern einen Termin in der Gastroenterologie in Fürth" das Werkzeug
`freie_termine_suchen` nicht aufgerufen. Einmal kam ein Text aus der
Wissensbasis, einmal **erfundene Termine** („Donnerstag, 2. Februar um 09:00").
Erfundene Termine sind im Praxisalltag gefährlich: Eine Person erscheint zu
einem Termin, den es nicht gibt.

Deshalb wird ein eindeutiger Terminwunsch – wie ein Notfall (Spec 006) –
**regelbasiert vor dem LLM** erkannt und ohne Modell beantwortet. Termine
kommen ausschließlich aus dem Terminsystem.

## Anforderungen

1. **Modul** `backend/app/leitplanken/terminwunsch.py` mit einer reinen
   Funktion (ohne Datenbank, ohne LLM), die eine Nachricht und den
   `StandortKatalog` bekommt und ein Ergebnis liefert. Vergleiche über
   `normalize()` aus Spec 002 (Groß-/Kleinschreibung, Umlaute).
2. **Erkennung** – ein Terminwunsch liegt vor, wenn die Nachricht
   - ein Wort enthält, das mit `termin` beginnt (`Termin`, `Termine`, `Terminanfrage` …), **und**
   - **genau eine Fachrichtung** aus dem Katalog nennt, **und**
   - **einen Ort** aus dem Katalog nennt.
   Eine Fachrichtung gilt als genannt, wenn ein Wort der Nachricht mit ihrem
   Namen beginnt oder – bei Namen auf `-ie` – mit dem Namen ohne `-ie`
   (`Neurologen` → Neurologie, `Kardiologin` → Kardiologie). Mehrwortnamen
   (`Innere Medizin`) müssen als Wortfolge vorkommen.
   Ein Ort gilt als genannt, wenn das Feld `ort` eines Standorts als ganzes
   Wort bzw. Wortfolge vorkommt; bei mehrteiligen Orten genügt das erste Wort
   (`Lauf` → Lauf an der Pegnitz).
   Fehlt eines der drei Merkmale, läuft der Chat **unverändert** wie bisher
   (z. B. „Was muss ich zum ersten Termin mitbringen?").
3. **Antworten** (alle mit `kategorie: "normal"`, Quelle
   `standorte.json`/„Standortverzeichnis", **ohne LLM-Aufruf**):
   - **Genau ein Standort** am Ort hat die Fachrichtung: Der Server ruft das
     Terminsystem auf (höchstens 5 Termine, wie das Werkzeug) und antwortet
     mit `aktion` vom Typ `termin_vorschlag`. Der Antworttext nennt den
     Standortnamen und die Fachrichtung, **aber keine Uhrzeiten** – die Termine
     zeigt die Oberfläche als Buttons.
   - **Mehrere Standorte** am Ort haben die Fachrichtung: Antwort nennt alle
     passenden Standortnamen und bittet, einen zu wählen; keine `aktion`.
   - **Kein Standort** am Ort hat die Fachrichtung: Antwort sagt das und nennt
     die Standorte im Verbund, die die Fachrichtung anbieten; keine `aktion`.
   - Liefert das Terminsystem keine freien Termine, sagt die Antwort das; keine `aktion`.
4. **Reihenfolge:** Notfall-Erkennung (Spec 006) zuerst, dann Terminwunsch,
   dann der bisherige LLM-Ablauf. Ein Notfall mit „Termin" bleibt ein Notfall.
5. **Leitplanke gegen erfundene Termine** im LLM-Ablauf: Enthält die Nachricht
   ein Wort, das mit `termin` beginnt, wurde `freie_termine_suchen` nicht
   erfolgreich aufgerufen, und enthält die Modellantwort eine Uhrzeit
   (`\b\d{1,2}[:.]\d{2}\b` oder `\b\d{1,2} Uhr\b`), ersetzt der Server die
   Antwort durch einen festen Text in `leitplanken/texte.py`:
   „Freie Termine kann ich Ihnen nur direkt aus dem Terminsystem zeigen. Bitte
   nennen Sie Fachrichtung und Ort, zum Beispiel: „Termin in der
   Gastroenterologie in Fürth"." Quellen entfallen. Log nur mit dem Hinweis
   auf die Leitplanke, ohne Nachrichteninhalt.
6. **pytest** für Erkennung (positive und negative Beispiele, inkl. Umlaute,
   Wortformen, mehrteiliger Ort), für alle Antwortfälle aus 3 und für die
   Leitplanke aus 5 (mit einem Stub-Provider, der eine Uhrzeit erfindet).
7. `docs/factory-log.md`: Eintrag mit Anlass (Generalprobe) und Ergebnis.
   `make eval` muss weiter die Schwellenwerte erreichen.
8. Die Abnahme ruft `/api/chat` jetzt öfter auf. Das Chat-Limit aus Spec 006
   (60 pro Minute) wird **nicht** geändert. Treten in `make acceptance` 429-Fehler
   auf, Ursache im Factory-Log und im PR beschreiben und aufhören.

## API-Vertrag

Keine neuen Endpunkte. `POST /api/chat` liefert für einen erkannten
Terminwunsch mit genau einem Standort:

```json
{
  "sitzung_id": "…",
  "antwort": "Hier sind freie Termine in der Gastroenterologie im MVZ Fürth Zentrum. …",
  "kategorie": "normal",
  "quellen": [{"dokument": "standorte.json", "titel": "Standortverzeichnis"}],
  "aktion": {"typ": "termin_vorschlag", "slots": [Slot, …]},
  "ki_hinweis": "…"
}
```

## Nicht im Umfang

- Rückfragen über mehrere Nachrichten (z. B. erst Ort, dann Fachrichtung) –
  der Verlauf wird wie bisher gespeichert, aber nicht für die Erkennung genutzt.
- Umgangssprache ohne Fachrichtungsnamen („Frauenarzt", „Hausarzt", „Magen-Darm")
- Datumswünsche („nächste Woche", „ab Montag")

## Umsetzungsnotizen

