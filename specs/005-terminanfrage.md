# Spec 005 – Terminanfrage über ein simuliertes Terminsystem

**Status:** fertig
**Abhängigkeiten:** 002, 004
**Abnahmetests:** `tests/acceptance/005_termine.robot` (Tag `spec-005`)

## Ziel

Patientinnen und Patienten können im Chat freie Termine finden und eine
Terminanfrage stellen. Das echte Terminsystem wird durch eine eigene,
austauschbare Termin-API simuliert.

Wichtige Architekturentscheidung (Datenschutz): **Das LLM sieht keine
personenbezogenen Daten.** Es darf freie Termine suchen und vorschlagen.
Name, Geburtsdatum und Telefon gibt die Person in einem Formular ein, das
direkt an die Termin-API sendet.

## Anforderungen

1. **Termin-Schnittstelle** als eigenes Modul `backend/app/termine/` mit einer
   abstrakten Klasse `Terminsystem` und der Implementierung `SimuliertesTerminsystem`.
   Eine spätere Anbindung an ein echtes PVS ersetzt nur diese Implementierung.
2. **Freie Termine** werden deterministisch erzeugt: für jeden Standort und jede
   seiner Fachrichtungen, Montag bis Freitag, in den nächsten 14 Tagen ab
   heute (Zeitzone `Europe/Berlin`), im 30-Minuten-Raster innerhalb der
   Öffnungszeiten, letzter Beginn 30 Minuten vor Schluss – bei geteilten
   Öffnungszeiten (z. B. `08:00-12:00, 14:00-18:00`) für jedes Intervall einzeln. Etwa die Hälfte
   der Termine gilt als belegt, bestimmt durch einen `hashlib.sha256`-Hash aus
   `standort_id + fachrichtung + beginn` (also stabil zwischen Neustarts).
   `slot_id` = `"<standort_id>|<fachrichtung>|<beginn ISO 8601>"`.
   Bereits angefragte Termine und Termine in der Vergangenheit gelten ebenfalls
   als nicht frei und erscheinen nicht in `/api/termine/freie`.
3. **Terminanfragen** werden in der Tabelle `terminanfragen` gespeichert.
   Ein Termin kann nur einmal angefragt werden.
4. **Löschfrist:** Ein Hintergrundjob (oder Aufruf beim Start und stündlich)
   löscht Terminanfragen, die älter als 30 Tage sind.
5. **Chat-Integration:** Werkzeug `freie_termine_suchen` aus Spec 004 wird
   registriert und liefert höchstens 5 Termine. Wenn das Werkzeug genutzt wurde,
   enthält die `ChatAntwort` eine `aktion` vom Typ `termin_vorschlag` mit
   genau diesen Terminen. Das LLM selbst kann **keine** Anfrage anlegen.
6. **Logging:** Terminanfragen werden nur mit `anfrage_id` und `slot_id`
   protokolliert, nie mit Name, Geburtsdatum oder Telefon.

## API-Vertrag

| Methode | Pfad | Body / Antwort |
|---|---|---|
| GET | `/api/termine/freie?standort_id=&fachrichtung=&ab_datum=YYYY-MM-DD&limit=` | `200` Liste `Slot`, aufsteigend nach `beginn`; `limit` 1–50, Standard 10 |
| | | `404` bei unbekanntem `standort_id`; `422` wenn der Standort die Fachrichtung nicht hat |
| POST | `/api/termine/anfragen` | Body `Anfrage` → `201` `AnfrageAntwort` |
| | | `409` `{"detail": "Termin nicht mehr verfügbar"}` wenn der Slot belegt, schon angefragt, vergangen oder nicht existent ist |
| | | `422` bei ungültigen Daten oder `einwilligung_datenschutz` ≠ `true` |
| GET | `/api/termine/anfragen/{anfrage_id}` | `200` `AnfrageAntwort` oder `404` |

`fachrichtung` wird wie in Spec 002 verglichen (ohne Groß-/Kleinschreibung,
Umschreibung von Umlauten erlaubt), muss aber eindeutig genau eine
Fachrichtung des Standorts treffen; keine oder mehrere Treffer → `422`.

`beginn` ist ISO 8601 mit dem Offset von `Europe/Berlin` (`+01:00` bzw.
`+02:00` in der Sommerzeit), nie UTC/`Z`.

`Slot`: `{"slot_id": "…", "standort_id": "std-004", "standort_name": "MVZ Fürth Zentrum", "fachrichtung": "Gastroenterologie", "beginn": "2026-10-27T09:30:00+01:00"}`

`Anfrage`:

```json
{
  "slot_id": "std-004|Gastroenterologie|2026-10-27T09:30:00+01:00",
  "name": "Erika Mustermann",
  "geburtsdatum": "1970-05-14",
  "telefon": "+49 170 0000000",
  "einwilligung_datenschutz": true
}
```

Validierung: `name` 2–100 Zeichen; `geburtsdatum` gültiges Datum in der
Vergangenheit; `telefon` 6–30 Zeichen aus Ziffern, Leerzeichen, `+`, `-`, `/`.

`AnfrageAntwort`: `{"anfrage_id": "<uuid>", "status": "angefragt", "slot": Slot}`
(ohne personenbezogene Felder).

`aktion` in der `ChatAntwort`:
`{"typ": "termin_vorschlag", "slots": [Slot, …]}`

## Nicht im Umfang

- Bestätigung durch die Praxis, Absage, Erinnerungen per SMS
- Anbindung an ein echtes PVS oder Terminsystem

## Umsetzungsnotizen

Plan (2026-10-27):

1. Modul `backend/app/termine/`: Modelle (`Slot`, `Anfrage`, `AnfrageAntwort`), Fehlerklassen,
   abstrakte Klasse `Terminsystem`, Tabelle `terminanfragen` (SQLAlchemy).
2. `SimuliertesTerminsystem`: Öffnungszeiten parsen (auch geteilte Intervalle), Raster 30 min,
   Mo–Fr, heute + 13 Tage (`Europe/Berlin`), belegt per `sha256(standort_id+fachrichtung+beginn)`.
3. Fachrichtung wie Spec 002 (Teilstring, normalisiert), aber genau ein Treffer, sonst 422.
4. Anfrage: Slot-ID wird gegen die erzeugten Slots geprüft (kanonische Form, frei, Zukunft);
   Eindeutigkeit über `UNIQUE(slot_id)` in der DB → `409`.
5. Migration `0003_terminanfragen`; Löschfrist 30 Tage beim Start und stündlich (asyncio-Task).
6. Router `/api/termine/...` mit API-Vertrag; Logs nur mit `anfrage_id`/`slot_id`,
   Engine mit `hide_parameters=True`, damit DB-Fehler keine Formulardaten ins Log schreiben.
7. Werkzeug `freie_termine_suchen` (max. 5) im `Werkzeugkasten`; `ChatAntwort.aktion`
   `termin_vorschlag` mit den Slots des letzten erfolgreichen Aufrufs; Systemprompt ergänzen.
8. pytest: Slot-Erzeugung, Validierung, Speicher (SQLite in-memory), API, Werkzeug, Chat-Aktion.

Ergebnis (2026-10-27): `make lint` grün, `make test` 235/235, `make acceptance SPEC=005` 12/12,
`make acceptance` 42/42. `make acceptance-llm` einmal mit Ollama: 44/47
(005 „Chat schlägt freie Termine vor" rot, Details und Annahmen im Factory-Log).
