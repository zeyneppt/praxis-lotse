# Spec 002 – Standortsuche

**Status:** offen
**Abhängigkeiten:** 001
**Abnahmetests:** `tests/acceptance/002_standorte.robot` (Tag `spec-002`)

## Ziel

Patientinnen, Patienten und Mitarbeitende finden schnell den passenden Standort
nach Fachrichtung und Ort. Diese API ist später auch das Werkzeug, das der
Chat-Assistent für Standortfragen aufruft (Spec 004).

## Anforderungen

1. Die Standorte werden beim Start aus `/data/standorte.json` gelesen
   (Pfad über Umgebungsvariable `DATA_DIR`, Standard `/data`).
   Keine Datenbanktabelle nötig; die Daten werden im Speicher gehalten.
2. Filter `fachrichtung`: ohne Groß-/Kleinschreibung, Teilwort-Treffer auf
   jeder Fachrichtung des Standorts (`gastro` findet `Gastroenterologie`).
   Umlaute dürfen in der Eingabe auch umschrieben sein: `gynaekologie` findet
   `Gynäkologie`, `orthopaedie` findet `Orthopädie`.
3. Filter `ort`: ohne Groß-/Kleinschreibung, Teilwort-Treffer auf `ort`
   (`lauf` findet `Lauf an der Pegnitz`).
4. Beide Filter sind optional und kombinierbar (UND-Verknüpfung).
5. Ergebnisse sind nach `id` aufsteigend sortiert.
6. Ein unbekannter Filterwert ist kein Fehler: Antwort `200` mit leerer Liste.

## API-Vertrag

| Methode | Pfad | Antwort |
|---|---|---|
| GET | `/api/standorte?fachrichtung=&ort=` | `200` Liste von `Standort` |
| GET | `/api/standorte/{id}` | `200` `Standort` oder `404` `{"detail": "Standort nicht gefunden"}` |
| GET | `/api/fachrichtungen` | `200` alphabetisch sortierte Liste eindeutiger Fachrichtungen (Strings) |

`Standort` hat exakt die Felder aus `data/standorte.json`:
`id`, `name`, `ort`, `stadtteil` (String oder `null`), `adresse`, `plz`,
`telefon`, `fachrichtungen` (Liste), `oeffnungszeiten` (Objekt mit Schlüsseln
`mo`–`fr`), `barrierefrei` (bool).

## Nicht im Umfang

- Entfernungssuche nach Postleitzahl oder Koordinaten
- Bearbeiten von Standorten

## Umsetzungsnotizen

