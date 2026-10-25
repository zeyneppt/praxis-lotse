# CLAUDE.md – Arbeitsregeln für Coding-Agenten

Du arbeitest in **Praxis-Lotse**, einem Demo-Assistenten für einen MVZ-Verbund.
Der Mensch schreibt Spezifikationen und Akzeptanztests, du schreibst den Code.
Lies diese Datei vollständig, bevor du etwas änderst.

## Grundprinzip: Die Definition von „fertig" gehört dem Menschen

- Eine Spec ist **fertig**, wenn alle Robot-Framework-Tests mit ihrem Tag
  (`spec-NNN`) grün sind, `make test` grün ist und `make lint` keine Fehler meldet.
- **Du änderst niemals** Dateien unter `tests/acceptance/`, `eval/fragen.yaml`,
  `.claude/` oder diese Datei – auch nicht über die Shell (`sed`, `git checkout` usw.).
  Diese Dateien sind die Abnahmekriterien. Hältst du einen Test für falsch,
  hörst du auf und beschreibst das Problem in `docs/factory-log.md` und im PR.
- Du änderst in `specs/` nur den Abschnitt **Status** und **Umsetzungsnotizen**
  der Spec, an der du gerade arbeitest.
- Eine Spec pro Branch, ein Pull Request pro Spec. Keine Arbeit „auf Vorrat"
  für spätere Specs.

## Architektur (verbindlich)

| Teil | Technik | Ort |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 | `backend/` |
| Datenbank | PostgreSQL 16 mit pgvector | Docker Compose |
| Embeddings | lokal über `fastembed`, mehrsprachiges Modell (siehe Spec 003) | im Backend |
| LLM | Provider-Schnittstelle: `ollama` (lokal, Standard für Entwicklung), `anthropic` (optional), `fake` (Tests/CI) | `backend/app/llm/` |
| Frontend | React 18 + TypeScript + Vite | `frontend/` |
| Abnahmetests | Robot Framework, RequestsLibrary, Browser Library | `tests/acceptance/` |
| Unit-Tests | pytest | `backend/tests/` |

- Ports: Backend `8000`, Frontend `5173`, Postgres `5432`.
- Konfiguration nur über Umgebungsvariablen (siehe `.env.example`). Keine Secrets im Code.
- API-Felder sind **deutsch** und exakt so benannt wie in den Specs.
  Code-Bezeichner (Funktionen, Klassen, Variablen) sind englisch.
- Neue Abhängigkeiten nur, wenn eine Spec sie braucht. Begründe sie im PR.

## Datenschutz und Sicherheit (nicht verhandelbar)

- Es gibt **keine echten Patientendaten**. Alle Daten in `data/` sind fiktiv.
- Personenbezogene Daten aus Terminanfragen (Name, Geburtsdatum, Telefon)
  werden **niemals an das LLM gesendet** und **niemals geloggt**.
  Logs laufen durch `app.logging.redact()` (Spec 006).
- Der LLM-Systemprompt liegt in `backend/app/prompts/system.md`, nicht im Code verstreut.
- Notfall-Erkennung ist regelbasiert und läuft **vor** jedem LLM-Aufruf.
- Der Assistent gibt keine medizinische Beratung (keine Diagnosen, keine
  Medikamentenänderungen). Er verweist an Praxis, 116117 oder 112.

## Arbeitsweise

1. Lies die Spec und die zugehörigen Tests in `tests/acceptance/NNN_*.robot`.
2. Schreibe einen kurzen Plan in den Abschnitt **Umsetzungsnotizen** der Spec.
3. Implementiere in kleinen Schritten. Schreibe pytest-Tests für die Logik.
4. Führe aus: `make lint`, `make test`, `make acceptance SPEC=NNN`.
5. Bei roten Tests: Ursache finden und beheben. Tests nicht abschwächen,
   nicht überspringen, keine Sonderfälle nur für Testdaten einbauen.
6. Trage Auffälligkeiten (Fehlversuche, Annahmen, offene Fragen) in
   `docs/factory-log.md` ein – kurz und ehrlich.
7. Commit-Nachrichten: `spec(NNN): <was>`. Danach PR mit Zusammenfassung,
   Testergebnis und offenen Punkten.

## Befehle

```bash
make up              # Docker Compose starten (db, backend, frontend)
make down            # stoppen
make ingest          # Wissensdokumente in die Vektordatenbank laden
make lint            # ruff + mypy (Backend), eslint + tsc (Frontend)
make test            # pytest
make acceptance      # Robot-Tests ohne Tag "llm" für alle begonnenen/fertigen Specs (ohne API-Key)
make acceptance SPEC=003   # nur Tests mit Tag spec-003
make acceptance-llm  # alle Robot-Tests inkl. echter LLM-Aufrufe
make eval            # Retrieval-Evaluation (Spec 007)
```

Diese Make-Ziele entstehen in Spec 001. Bis dahin existieren sie noch nicht.
