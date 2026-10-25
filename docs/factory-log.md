# Factory-Log

Was beim Bauen tatsächlich passiert ist – auch das, was schiefging.
Ein Eintrag pro Spec. Neue Einträge oben.

Vorlage:

```markdown
## Spec NNN – <Titel> (<Datum>)

- Durchläufe bis alle Tests grün: <n>
- Fehler des Agenten und wie sie erkannt wurden:
  - <z. B. „Fachrichtungsfilter war case-sensitiv – vom Robot-Test 002 gefunden">
- Getroffene Annahmen:
  - ...
- Eingriffe durch den Menschen:
  - <z. B. „Spec präzisiert, weil Öffnungszeiten-Format unklar war">
- Review-Ergebnis: freigegeben nach <n> Runden
```

---

<!-- Einträge ab hier -->

## Spec 003 – Wissensbasis und semantische Suche (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 9/9 im ersten Lauf, `make acceptance` 23/23);
  `make lint` brauchte 3 Läufe, `make test` 74/74 (nach Review-Fix).
- Fehler des Agenten und wie sie erkannt wurden:
  - Import-Reihenfolge in `app/main.py` (ruff I001) und eine von `ruff format` anders
    umbrochene Testsignatur – von `make lint` gefunden.
  - Falscher `type: ignore`-Code in einem pytest-Test (mypy strict meldete `no-untyped-call`);
    jetzt mit `ClauseElement` typisiert.
  - Eine `frage` nur aus Leerzeichen lieferte 200 mit beliebigen Treffern statt 422 – derselbe
    Fehlertyp wie in Spec 002, vom Reviewer gefunden. Behoben mit
    `StringConstraints(strip_whitespace=True, …)`, pytest-Fälle `"   "` und `"\n\t"` ergänzt.
- Getroffene Annahmen:
  - Neue Abhängigkeiten: `fastembed` (Spec verlangt es), `pgvector` (SQLAlchemy-Typ `Vector`
    und `cosine_distance`), `pyyaml` (YAML-Kopf), dev: `types-PyYAML`.
  - `inhalt_hash` = SHA-256 über Modellname + Einbettungstext (`"<titel> – <abschnitt>\n\n<text>"`).
    Ein Modellwechsel bettet so alles neu ein. Abgleich über `(dokument, inhalt_hash)`:
    Ein geänderter Abschnitt zählt als 1 neu + 1 gelöscht. `position` und `fachrichtungen`
    (nicht eingebettet) werden bei unveränderten Abschnitten aktualisiert.
  - „gelöscht" zählt alle entfernten Abschnitte (gelöschte Dateien und geänderte Abschnitte).
    Manuell geprüft mit einer Kopie von `data/wissen` ohne `termin-absagen.md`:
    `0 neu, 29 unverändert, 4 gelöscht`; danach mit Originaldaten `4 neu, 29 unverändert, 0 gelöscht`.
  - Spalte `embedding vector(384)` fest (Dimension des Standardmodells). Liefert ein anderes
    `EMBEDDING_MODEL` eine andere Dimension, bricht der Ingest mit klarer Meldung ab;
    dann braucht es eine neue Migration.
  - Zusätzliche Spalte `position` (Reihenfolge im Dokument); die Spec nennt „mindestens" die Felder.
  - Leere Abschnitte werden mitgezählt (ein Abschnitt pro `##`, wie in der Spec); `###` trennt nicht.
  - „Höchstens 2 pro Dokument" per `row_number() OVER (PARTITION BY dokument …)` über alle
    Abschnitte. Das nutzt den HNSW-Index nicht, ist aber exakt; bei 33 Abschnitten ~1 ms.
    Der Index existiert wie gefordert für spätere größere Datenmengen.
  - Das Modell wird im Dockerfile geladen (`FASTEMBED_CACHE_PATH=/opt/fastembed`), danach
    `HF_HUB_OFFLINE=1`. Der Backend-Start lädt das Modell aus dem Cache in den Speicher
    (Lifespan), nicht beim ersten Request. `docker-compose.yml` reicht `EMBEDDING_MODEL` als
    Build-Argument durch.
  - Logging: Spec 006 (`redact()`) gibt es noch nicht. Die Suche loggt nur Trefferzahl und Dauer;
    ein pytest-Test prüft, dass der Fragetext nicht im Log steht. Damit App-Logs überhaupt
    erscheinen, setzt `app/main.py` `logging.basicConfig(level=INFO)` (Uvicorn konfiguriert nur
    seine eigenen Logger). Spec 006 ersetzt das durch den Redaktionsfilter.
  - `GET /api/wissen/dokumente` gruppiert nach `dokument` (Titel per `min()`, nach Ingest ohnehin eindeutig).
  - README-Statustabelle: 002 und 003 auf `fertig` gesetzt (002 war nach dem Merge noch `offen`).
- Offene Punkte:
  - Das Modell schneidet Eingaben nach 128 Token ab. 1 von 33 Abschnitten ist länger
    („Ernährung in den Tagen davor", 159 Token): Der Absatz zu klaren Flüssigkeiten am Vortag
    fließt nicht ins Embedding ein (der Text im Treffer ist vollständig). Kandidat für die
    Eval in Spec 007 (z. B. Chunking nach Absätzen oder anderes Modell).
  - Scores im Abstand: „Koloskopie essen" → darmspiegelung 0,734 vs. magenspiegelung 0,605;
    „Termin absagen" → termin-absagen 0,793 vs. 0,561. Die Tests sind also nicht knapp.
  - Das Docker-Image wächst durch fastembed/onnxruntime und das Modell (~220 MB).
- Eingriffe durch den Menschen:
  - keine
- Review-Ergebnis: ausstehend

## Spec 002 – Standortsuche (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 11/11 im ersten Lauf, `make acceptance` 14/14);
  `make lint` brauchte 2 Läufe.
- Fehler des Agenten und wie sie erkannt wurden:
  - Docstring in `app/standorte.py` war länger als 100 Zeichen – von `make lint` (ruff E501) gefunden.
  - Ein Filter nur aus Leerzeichen (`?fachrichtung=%20`) galt nicht als leer und fand alle
    Standorte mit Leerzeichen in der Fachrichtung („Innere Medizin") – entgegen der eigenen
    Annahme unten. Vom Reviewer gefunden, behoben (`strip()`, danach leer = kein Filter).
  - Zerlegte Umlaute (NFD, z. B. von macOS) wurden nicht umschrieben, `gynäk` in NFD fand
    nichts – vom Reviewer gefunden, behoben (`unicodedata.normalize("NFC", …)` vor dem Vergleich).
  - Nach dem Fix formatierte `ruff format` eine Testzeile anders – von `make lint` gefunden.
- Getroffene Annahmen:
  - Die Umlaut-Umschreibung (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`, plus `casefold()`) gilt für
    `fachrichtung` **und** `ort` (`nuernberg` findet `Nürnberg`). Die Spec verlangt sie nur
    für `fachrichtung`; eine gemeinsame Vergleichsfunktion ist einfacher und widerspricht Anf. 3 nicht.
  - Leerer Filterwert (`?fachrichtung=`) oder nur Leerzeichen wirkt wie kein Filter;
    Leerzeichen am Rand werden entfernt.
  - `fachrichtung` und `ort` sind auf 100 Zeichen begrenzt (`Query(max_length=100)`); längere
    Werte liefern `422` (FastAPI-Standard). Die Spec nennt keine Grenze; Vorschlag des Reviewers
    als Eingabeprüfung vor Spec 004.
  - `/api/fachrichtungen` sortiert nach der normalisierten Form, damit ein Wort mit Umlaut am
    Anfang (z. B. `Ärztlicher …`) bei `A` einsortiert wird und nicht hinter `Z`.
  - Das Modell `Standort` lehnt unbekannte Felder ab (`extra="forbid"`): Weicht
    `standorte.json` vom Vertrag ab, startet das Backend nicht, statt Felder still zu verwerfen.
  - `DATA_DIR` in `.env.example` ergänzt (Standard `/data`).
- Offene Punkte:
  - Der Katalog wird nur beim Start geladen; Änderungen an `standorte.json` brauchen einen Neustart
    (laut Spec so gewollt).
- Eingriffe durch den Menschen:
  - Nach dem Review: alle drei Hinweise (Leerzeichen, NFC, Längengrenze) mit pytest-Fällen
    in diesen PR aufnehmen.
- Review-Ergebnis: freigegeben nach 1 Runde (keine blockierenden Punkte, Hinweise im PR-Kommentar).
  Drei Hinweise danach umgesetzt; `make lint` grün, `make test` 43/43 (lokal und im Container),
  `make acceptance` 14/14 (spec-002 11/11).

## Spec 001 – Projektgerüst, lokale Umgebung und CI (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 3/3 im ersten Lauf); `make lint` brauchte 3 Läufe.
- Fehler des Agenten und wie sie erkannt wurden:
  - ruff/isort hielt `alembic` wegen des Verzeichnisses `backend/alembic/` für ein
    eigenes Paket und wollte die Imports umsortieren – von `make lint` gefunden,
    behoben mit `known-third-party = ["alembic"]` statt die Imports anzupassen.
  - Überflüssiges `# type: ignore` in einem pytest-Test – von mypy (strict) gefunden,
    Test nutzt jetzt `Settings.model_validate(...)`.
- Getroffene Annahmen:
  - `make lint`/`make test` laufen lokal in `backend/.venv` (wird automatisch angelegt),
    nicht im Container – so braucht der CI-Job `lint-und-test` kein Docker. In der README beschrieben.
  - `LLM_PROVIDER` ist auf `fake | ollama | anthropic` beschränkt; ein anderer Wert lässt
    das Backend beim Start scheitern. Standard ohne Angabe: `fake`.
  - Bei Datenbankfehler ist `status` weiterhin `"ok"` (der Prozess läuft), nur
    `datenbank` wird `"fehler"` und der HTTP-Status `503` – so steht es im API-Vertrag.
    Manuell geprüft durch Stoppen des `db`-Containers.
  - Ist die DB beim Start nicht erreichbar, schlagen die Migrationen fehl und das Backend
    startet nicht; `depends_on: service_healthy` verhindert das im Normalfall.
  - CI-Job `eval` existiert schon, prüft aber zuerst, ob Spec 007 `fertig` ist, und
    überspringt sich sonst.
  - Lokal läuft Node 26; im Frontend-Container und in der CI Node 22 (LTS).
- Offene Punkte:
  - pytest meldet eine `StarletteDeprecationWarning` (httpx im TestClient); harmlos, nicht behoben.
  - `alembic/env.py` kennt keinen Offline-Modus (`alembic upgrade head --sql` baut trotzdem
    eine Verbindung auf); ggf. `context.is_offline_mode()` ergänzen.
  - Der CI-Job `geschuetzte-dateien` greift nur bei PRs. Direkte Pushes auf `main` brauchen
    Branch Protection mit Required Checks (Repo-Einstellung, Mensch). Optional
    `git diff --no-renames`, damit Verschiebungen eindeutig erkannt werden.
  - `--host 0.0.0.0` steht mehrfach (package.json, frontend/Dockerfile, docker-compose.yml,
    vite.config.ts); eine Stelle reicht. Ohne Source-Mount kein Hot Reload im Frontend-Container.
  - `CORS_ORIGINS` ist per Umgebungsvariable setzbar, fehlt aber in `.env.example`.
  - `DATABASE_URL` hat einen Default in `backend/app/config.py`; langfristig Pflichtvariable ohne Default.
- Eingriffe durch den Menschen:
  - Nach dem Review: `connect_timeout` und Dockerfile-Fix noch in diesen PR aufnehmen,
    übrige Hinweise als offene Punkte festhalten.
- Review-Ergebnis: freigegeben nach 1 Runde (keine blockierenden Punkte, Hinweise im PR-Kommentar).
  Zwei Hinweise danach umgesetzt:
  - `connect_timeout` von 3 s in `app/db.py` – im Container gegen einen nicht erreichbaren Host
    geprüft: `database_reachable()` liefert nach 3,0 s `False`, statt zu hängen.
  - `backend/Dockerfile` installiert editable (`pip install -e`), damit `app` aus `/app/app`
    importiert wird und `ALEMBIC_DIR` auf `/app/alembic` zeigt. Neuer pytest-Test prüft,
    dass das Migrationsverzeichnis gefunden wird (Head `0001`); läuft auch im Container grün.

## Nachtrag (Mensch) – Spec 001

- Der Agent wollte beim Einlesen `.env` mit `.env.example` vergleichen. Die Regel `Read(./.env)` in `.claude/settings.json` hat das blockiert – Schutz wirkt wie vorgesehen.
- Redundante `Write(...)`-Deny-Regeln entfernt (Claude Code deckt Schreiben über `Edit(...)` ab).
