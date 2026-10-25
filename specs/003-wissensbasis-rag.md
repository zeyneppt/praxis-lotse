# Spec 003 – Wissensbasis und semantische Suche (RAG-Retrieval)

**Status:** fertig
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

Plan:
1. Abhängigkeiten `fastembed` (Embeddings), `pgvector` (SQLAlchemy-Typ `Vector`),
   `pyyaml` (YAML-Kopf). `EMBEDDING_MODEL` in `app/config.py`.
2. Migration `0002`: Tabelle `wissen_abschnitte` (Spec-Felder plus `position`),
   `embedding vector(384)`, HNSW-Index mit `vector_cosine_ops`.
3. `app/wissen.py`: YAML-Kopf lesen, Chunking pro `##`-Überschrift (Text davor verworfen),
   Einbettungstext `"<titel> – <abschnitt>\n\n<text>"`, `inhalt_hash` = SHA-256 über Modellname
   und Einbettungstext.
4. `app/embeddings.py`: dünne Hülle um `fastembed.TextEmbedding`, im Lifespan geladen,
   per Dependency in pytest durch ein Fake ersetzbar.
5. `app/ingest.py` (`python -m app.ingest`): Abgleich über `(dokument, inhalt_hash)`;
   nur neue Abschnitte werden eingebettet, nicht mehr vorhandene gelöscht.
   Ausgabe: neu / unverändert / gelöscht. `make ingest` ruft das im Container auf.
6. Suche: Kosinus-Distanz `<=>`, höchstens 2 Treffer pro Dokument (Fensterfunktion),
   `score = round(1 − Distanz, 3)`; Log nur Dauer und Trefferzahl.
7. `app/api_wissen.py`: `POST /api/wissen/suche` (Validierung 1–500 Zeichen, k 1–10),
   `GET /api/wissen/dokumente`.
8. Dockerfile: Build-Argument `EMBEDDING_MODEL`, Modell beim Build laden, danach offline;
   `docker-compose.yml` reicht das Build-Argument durch.
9. pytest: Chunking, Hash, Ingest-Abgleich, Validierung, Score, Logging ohne Fragetext.
10. Container bauen, `make ingest`, `make lint`, `make test`, `make acceptance SPEC=003`, `make acceptance`.

Ergebnis: `make lint` grün, `make test` 79/79, `make acceptance SPEC=003` 9/9,
`make acceptance` 23/23. Annahmen und offene Punkte siehe `docs/factory-log.md`.
