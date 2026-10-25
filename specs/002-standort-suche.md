# Spec 002 – Standortsuche

**Status:** fertig
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

Plan:
1. `DATA_DIR` (Standard `/data`) in `app/config.py` und `.env.example`.
2. `app/standorte.py`: Pydantic-Modelle `Standort`/`Oeffnungszeiten` (`extra="forbid"`,
   damit Vertrag und Datei übereinstimmen), Laden von `standorte.json`, Klasse `StandortKatalog`.
3. Normalisierung für Filter: `casefold()` plus `ä→ae`, `ö→oe`, `ü→ue`, `ß→ss` auf beiden Seiten,
   dann Teilwort-Vergleich; gilt für `fachrichtung` und `ort`.
4. Filter optional, UND-verknüpft, leerer Wert = kein Filter; Ergebnis nach `id` sortiert.
5. `app/api_standorte.py`: Router mit `/api/standorte`, `/api/standorte/{id}`, `/api/fachrichtungen`.
6. Katalog wird im Lifespan geladen und in `app.state` gehalten; Zugriff per Dependency
   (in pytest überschreibbar).
7. pytest: Normalisierung, Filter, Sortierung, 404, Fachrichtungen, Laden der echten Datendatei.
8. Container neu bauen, `make lint`, `make test`, `make acceptance SPEC=002`, dann `make acceptance`.

