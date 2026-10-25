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
