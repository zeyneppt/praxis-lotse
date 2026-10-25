# Spec 001 – Projektgerüst, lokale Umgebung und CI

**Status:** fertig
**Abhängigkeiten:** keine
**Abnahmetests:** `tests/acceptance/001_projektgeruest.robot` (Tag `spec-001`)

## Ziel

Ein lauffähiges, leeres Gerüst aus Backend, Frontend und Datenbank, das mit
einem Befehl startet, plus eine CI-Pipeline, die ab jetzt jeden Pull Request prüft.

## Anforderungen

1. **Docker Compose** (`docker-compose.yml`) mit drei Diensten:
   - `db`: Image `pgvector/pgvector:pg16`, Benutzer/Passwort/DB `lotse`, Port 5432,
     Healthcheck mit `pg_isready`.
   - `backend`: baut aus `backend/Dockerfile`, Port 8000, liest `.env`
     (`env_file` mit `required: false`, damit die CI ohne `.env` startet),
     startet erst, wenn `db` gesund ist. Mountet `data/` schreibgeschützt nach `/data`.
     `extra_hosts: ["host.docker.internal:host-gateway"]`, damit das Backend
     ein auf dem Host laufendes Ollama erreicht (auch unter Linux).
   - `frontend`: baut aus `frontend/Dockerfile`, Vite-Dev-Server auf Port 5173,
     erreichbar von außen (`--host 0.0.0.0`).
2. **Backend** (`backend/`): FastAPI-App in `backend/app/main.py`, Abhängigkeiten
   über `backend/pyproject.toml`. CORS erlaubt `http://localhost:5173`.
   Datenbankmigrationen mit Alembic; beim Start werden ausstehende Migrationen
   ausgeführt. Die Extension `vector` wird in der ersten Migration aktiviert.
3. **Frontend** (`frontend/`): React 18 + TypeScript + Vite. Startseite mit
   Überschrift „Praxis-Lotse" als `<h1>`.
4. **Makefile** im Wurzelverzeichnis mit den Zielen aus `CLAUDE.md`:
   `up`, `down`, `ingest`, `lint`, `test`, `acceptance`, `acceptance-llm`, `eval`.
   - `make acceptance` führt Robot aus:
     `robot --outputdir reports/robot --exclude llm <Include-Liste> tests/acceptance`
   - Die Include-Liste: mit `SPEC=NNN` genau `--include spec-NNN`. Ohne `SPEC`
     ein `--include spec-NNN` für **jede Spec, deren Statuszeile `fertig` oder
     `in Arbeit` lautet**. Das ermittelt ein kleines Skript
     `scripts/aktive_specs.sh`, das die Zeile `**Status:**` in `specs/0*.md` liest.
     So laufen nur Tests für bereits begonnene Specs, und Tests späterer Specs
     blockieren die CI nicht. Ist keine Spec aktiv, endet `make acceptance` mit Code 0.
   - `make ingest` und `make eval` laufen über `docker compose exec -T backend …`
     (ohne TTY, damit sie auch aus Robot und CI funktionieren).
   - `make acceptance-llm` dasselbe, aber mit `--exclude fake-only` statt
     `--exclude llm` (läuft gegen ein Backend mit `LLM_PROVIDER=ollama` oder `anthropic`).
   - Ziele, deren Spec noch nicht umgesetzt ist (`ingest`, `eval`), geben vorerst
     eine Meldung aus und beenden sich mit Code 0.
   - `make test` führt pytest im Backend-Container oder in einer lokalen venv aus;
     der gewählte Weg ist in der README beschrieben.
5. **Lint:** `ruff` und `mypy` für das Backend, `eslint` und `tsc --noEmit` für das Frontend.
6. **CI** (`.github/workflows/ci.yml`), läuft bei jedem Push und Pull Request:
   1. Job `geschuetzte-dateien` (nur bei Pull Requests): schlägt fehl, wenn der PR
      Dateien unter `tests/acceptance/`, `eval/fragen.yaml`, `.claude/` oder `CLAUDE.md` ändert,
      **außer** der PR trägt das Label `abnahme-aenderung`.
   2. Job `lint-und-test`: `make lint` und `make test`.
   3. Job `abnahme`: `cp .env.example .env`, dann `docker compose up -d --build` mit `LLM_PROVIDER=fake`,
      wartet bis `/api/health` antwortet, installiert
      `tests/acceptance/requirements.txt`, führt `rfbrowser init chromium` aus,
      dann `make ingest` und `make acceptance`. Lädt `reports/robot/` als Artefakt hoch.
   4. Job `eval` (sobald Spec 007 fertig ist): `make eval`.
7. **Health-Endpunkt** (siehe API-Vertrag).

## API-Vertrag

| Methode | Pfad | Antwort |
|---|---|---|
| GET | `/api/health` | `200` `{"status": "ok", "datenbank": "ok", "llm_provider": "<fake\|ollama\|anthropic>"}` |

`datenbank` ist `"ok"`, wenn ein `SELECT 1` gegen Postgres gelingt, sonst
`"fehler"` (dann Status `503`).

## Nicht im Umfang

- fachliche Endpunkte (ab Spec 002)
- Deployment in die Cloud

## Umsetzungsnotizen

Plan:

1. `docker-compose.yml` mit `db` (pgvector/pg16, Healthcheck), `backend`, `frontend`.
2. Backend: FastAPI in `backend/app/main.py`, Konfiguration über `pydantic-settings`
   (`app/config.py`), DB-Engine in `app/db.py`, `GET /api/health`.
3. Alembic in `backend/alembic/`, erste Migration `CREATE EXTENSION vector`;
   beim Start (Lifespan) `alembic upgrade head`.
4. pytest-Tests für Health (ok/503, Provider) mit überschriebener DB-Prüfung.
5. Frontend: Vite + React 18 + TS, `<h1>Praxis-Lotse</h1>`, eslint + `tsc --noEmit`.
6. `scripts/aktive_specs.sh` liest `**Status:**` aus `specs/0*.md`.
7. Makefile mit `up down ingest lint test acceptance acceptance-llm eval`;
   `lint`/`test` laufen lokal in `backend/.venv` (wird bei Bedarf angelegt).
8. CI `.github/workflows/ci.yml` mit Jobs `geschuetzte-dateien`, `lint-und-test`,
   `abnahme`, `eval` (deaktiviert bis Spec 007).
9. README: Weg für `make test` beschreiben.

