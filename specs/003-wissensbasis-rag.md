# Spec 003 – Wissensbasis und semantische Suche (RAG-Retrieval)

**Status:** offen
**Abhängigkeiten:** 001
**Abnahmetests:** `tests/acceptance/003_wissen.robot` (Tag `spec-003`)

## Ziel

Fragen von Patientinnen und Patienten („Was darf ich vor der Darmspiegelung
essen?") finden die passenden Abschnitte in den Praxisdokumenten, auch wenn
andere Wörter verwendet werden als im Dokument. Das ist der Retrieval-Teil von
RAG; die Antwortformulierung folgt in Spec 004.

## Anforderungen

1. **Quellen:** alle `*.md`-Dateien in `/data/wissen/`. Jede Datei hat einen
   YAML-Kopf mit `titel`, `fachrichtungen`, `stand`.
2. **Aufteilung (Chunking):** ein Abschnitt pro `##`-Überschrift. Der Text vor
   der ersten `##`-Überschrift (Hinweiskasten) wird nicht indexiert.
   Jeder Abschnitt wird zusammen mit Dokumenttitel und Abschnittsüberschrift
   eingebettet (`"<titel> – <abschnitt>\n\n<text>"`).
3. **Embeddings lokal** mit `fastembed`, Modell aus `EMBEDDING_MODEL`
   (Standard siehe `.env.example`). Es werden keine Texte an externe Dienste
   gesendet. Das Modell wird beim Docker-Build heruntergeladen, nicht beim
   ersten Request (Build-Argument `EMBEDDING_MODEL` mit demselben Standardwert
   wie in `.env.example`).
4. **Speicherung:** Tabelle `wissen_abschnitte` in Postgres mit pgvector-Spalte,
   Felder mindestens `id`, `dokument` (Dateiname), `titel`, `abschnitt`, `text`,
   `fachrichtungen`, `inhalt_hash`, `embedding`. Index für Kosinus-Distanz.
5. **Ingest:** `make ingest` ruft einen CLI-Befehl im Backend-Container auf
   (`python -m app.ingest`). Der Ingest ist **idempotent**: Abschnitte mit
   unverändertem `inhalt_hash` werden nicht neu eingebettet; Abschnitte
   gelöschter Dateien werden entfernt. Ausgabe: Anzahl neu, unverändert, gelöscht.
6. **Suche:** Kosinus-Ähnlichkeit, Ergebnis sortiert nach `score` absteigend,
   `score` = 1 − Kosinus-Distanz, gerundet auf 3 Nachkommastellen.
   Pro Dokument höchstens 2 Treffer, damit die Top-Ergebnisse vielfältig sind.
7. **Logging:** Jede Suche protokolliert Dauer und Anzahl der Treffer, aber
   **nicht** den Fragetext (über `redact()`, sobald Spec 006 existiert).

## API-Vertrag

| Methode | Pfad | Body / Antwort |
|---|---|---|
| POST | `/api/wissen/suche` | Body `{"frage": "<1–500 Zeichen>", "k": <1–10, Standard 3>}` |
| | | `200` `{"treffer": [Treffer, …]}` |
| | | `422` bei leerer, zu langer oder fehlender `frage`, oder `k` außerhalb 1–10 |
| GET | `/api/wissen/dokumente` | `200` Liste `{"dokument", "titel", "abschnitte": <Anzahl>}`, sortiert nach `dokument` |

`Treffer`: `{"dokument": "darmspiegelung-vorbereitung.md", "titel": "…",
"abschnitt": "…", "text": "…", "score": 0.731}`

## Nicht im Umfang

- PDF- oder Word-Dokumente
- Hybride Suche (Volltext + Vektor) – kann eine spätere Spec sein, wenn die Eval es nahelegt

## Umsetzungsnotizen

