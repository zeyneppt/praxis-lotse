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

## Spec 004 – Chat-Assistent mit Werkzeugen (2026-10-25)

- Durchläufe bis alle Tests grün: 1 für `make acceptance SPEC=004` (7/7 im ersten Lauf,
  `make acceptance` 30/30); `make lint` 2 Läufe, `make test` 151/151.
  Zusätzlich 7 Läufe der `llm`-Tests gegen Ollama (qwen2.5:7b): 8/11 → 9/11 → 10/11 →
  10/11 → 9/11 → 10/11 und 11/11 (siehe unten).
- Fehler des Agenten und wie sie erkannt wurden:
  - Zwei Zeilen über 100 Zeichen – von `make lint` (ruff E501) gefunden.
  - pytest-Tests übergaben `httpx.Client` an die SDKs; `openai` 3.x und `anthropic` 2.x
    nutzen `httpx2` und lehnen das ab – vom pytest-Lauf und mypy gefunden, Tests nutzen
    jetzt `httpx2.MockTransport` (kommt mit den SDKs, keine eigene Abhängigkeit).
  - Erster Systemprompt: qwen2.5:7b rief in den `llm`-Tests gar keine Werkzeuge auf und
    antwortete aus eigenem Wissen (Log: „0 Werkzeugaufrufe"). Ein Vergleich direkt gegen
    Ollama (je Variante 6–20 Anfragen) zeigte: Kein einzelner Abschnitt ist schuld,
    `tool_choice: "required"` ignoriert Ollama, eine Erinnerung als Folgenachricht hilft nicht.
    Eine Regel ganz oben im Prompt hebt die Quote auf ~70 %, nicht auf 100 %.
    Deshalb zusätzlich die Rückfallsuche im Code (siehe Annahmen).
  - Qwen lieferte Werkzeugaufrufe teils als Text, mit verstümmeltem öffnendem Tag
    („onaut", „isphere" statt `<tool_call>`); Ollama erkannte sie nicht. Mein erster Parser
    suchte nur das korrekte Tag – durch Zeitmessung des Sitzungs-Tests gefunden, jetzt zählt
    jedes JSON-Objekt `{"name": <Text>, "arguments": …}` in der Antwort.
  - `LLM_TIMEOUT_SECONDS=30` war zu knapp: Die Antwortrunde dauert auf diesem Rechner
    27–30 s (~1700 Prompt-Tokens, ~150 Antwort-Tokens) – vom Log (`APITimeoutError`) und einer
    Messung gefunden. Standard jetzt 60.
- Getroffene Annahmen:
  - Neue Abhängigkeiten: `openai` (Ollama über die OpenAI-kompatible Schnittstelle, später
    Azure über `base_url`) und `anthropic` – beide verlangt die Spec.
  - Neue Einstellung `LLM_TIMEOUT_SECONDS` (Standard 60, in `.env.example`). `OLLAMA_BASE_URL`
    wird in `docker-compose.yml` mit Standard `http://host.docker.internal:11434/v1` durchgereicht.
    SDK-Wiederholungen: Ollama 0, Anthropic 1.
  - **Quellen** („gegeben **und** gestützt"): Das Modell nennt in einer letzten Zeile
    `Quellen: <dokument>, …`; der Server entfernt die Zeile und übernimmt nur Dokumente, die
    das Modell tatsächlich bekommen hat (Dateiname oder Titel). `Quellen: keine` → `[]`.
    Fehlt die Zeile oder passt sie zu keinem Dokument, zählen alle gelieferten Dokumente.
    `standorte.json` gilt als geliefert, wenn `standorte_suchen` mindestens einen Standort fand.
  - **Rückfallsuche:** Antwortet das Modell in der ersten Runde ohne Werkzeug, verwirft der
    Server die Antwort, ruft `wissen_suchen(frage=<Nachricht>)` auf und lässt das Modell
    erneut antworten. Begründung: „antwortet nur auf Grundlage dieser Ergebnisse" wiegt
    schwerer als „entscheidet selbst"; wenn das Modell Werkzeuge nutzt, entscheidet es weiter selbst.
    Nebenwirkung: Auch Grüße („Hallo") lösen eine Suche aus (eine LLM-Runde mehr).
  - Werkzeuglimit: 4 Aufrufe pro Nachricht. Weitere Aufrufe derselben Antwort bekommen ein
    Fehlerergebnis (jeder Aufruf braucht eines), danach eine Runde mit `tool_choice: none`;
    liefert das Modell trotzdem Aufrufe, zählt nur sein Text.
  - Sitzungen speichern nur Nutzernachrichten und Antworttexte, keine Werkzeugaufrufe/-ergebnisse;
    gekürzt wird paarweise, damit der Verlauf mit einer Nutzernachricht beginnt. Fehlerantworten
    (`kategorie: "fehler"`) kommen nicht in den Verlauf. Eine unbekannte `sitzung_id` startet
    eine neue Sitzung unter dieser ID; eine `sitzung_id`, die keine UUID ist, ergibt `422`.
  - `nachricht` wird vor der Längenprüfung getrimmt (nur Leerzeichen → `422`), wie in Spec 003.
  - Die Fehlermeldung verweist allgemein auf „Ihren Standort", weil es keine zentrale Nummer gibt.
  - Logs: nur Länge der Nachricht, Zahl der Werkzeugaufrufe und Quellen bzw. der Fehlertyp;
    ein pytest-Test prüft, dass der Nachrichtentext nicht im Log steht. Werkzeugfehler an das
    Modell enthalten nur Feldnamen und Fehlertypen, keine Eingabewerte.
  - Prompt-Injection-Kennzeichnung und Kanarien-Prüfung der Antwort gehören zu Spec 006;
    der Systemprompt enthält die Kennung bereits mit dem Verbot, sie auszugeben.
- Offene Punkte:
  - Die `llm`-Tests sind mit qwen2.5:7b nicht stabil grün. Sporadisch: „Unbekanntes wird nicht
    erfunden" (Modell sagt richtig „keine Standorte", verweist aber nicht aufs Telefon) und
    „Wissensfrage …" (nennt die 24 Stunden nicht). Ein größeres Modell oder Anthropic dürfte
    das beheben; nicht geprüft (kein API-Key verwendet).
  - Auf langsamer Hardware kann eine Anfrage mit mehreren Runden das 60-s-Zeitlimit der
    Robot-Session überschreiten. Ein Gesamtbudget pro Anfrage wäre eine Option.
  - Der Sitzungsspeicher ist pro Prozess; mit mehreren Uvicorn-Workern fänden Folgeanfragen
    ihren Verlauf nicht immer (laut Spec nur im Speicher, daher so gelassen).
  - Ein Datenbankfehler während eines Werkzeugaufrufs ergibt `500` (kein Anbieterfehler im
    Sinne von Anforderung 6).
- Eingriffe durch den Menschen: keine.
- Review-Ergebnis: steht aus.

## Spec 003 – Wissensbasis und semantische Suche (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 9/9 im ersten Lauf, `make acceptance` 23/23);
  `make lint` brauchte 3 Läufe, `make test` 79/79 (nach Review-Fixes).
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
  - Für Spec 006: Die Standard-422-Antwort von FastAPI enthält im Feld `input` den Eingabewert,
    bei zu langer `frage` also den kompletten Fragetext (geht nur an den Client zurück, nicht ins Log).
    Klären, ob Validierungsfehler Eingaben zurückgeben dürfen; sonst eigener
    `RequestValidationError`-Handler ohne `input`.
- Eingriffe durch den Menschen:
  - Nach dem Review: Hinweise 1 und 2 in diesen PR aufnehmen, Hinweis 3 als offenen Punkt für Spec 006.
    - `make ingest` bricht ab (Exit-Code 1, Meldung „Ingest abgebrochen, nichts gelöscht: …"),
      wenn `/data/wissen` fehlt oder keine `*.md` enthält. Die Dokumente werden vor jedem
      Datenbank- oder Modellzugriff gelesen; pytest prüft, dass weder Migrationen, Engine noch
      Modell angefasst werden. Im Container geprüft: beide Fälle Exit 1, danach weiterhin
      `0 neu, 33 unverändert, 0 gelöscht`.
    - Wissensdokumente werden mit `utf-8-sig` gelesen; pytest-Fall mit BOM.
- Review-Ergebnis: freigegeben nach 2 Runden. Runde 1: ein blockierender Punkt (Frage nur aus
  Leerzeichen → 200 statt 422), behoben. Runde 2: keine blockierenden Punkte. Hinweise
  im PR-Kommentar; zwei davon auf Wunsch des Menschen umgesetzt (siehe Eingriffe).

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
