# Praxis-Lotse

Ein KI-Assistent für einen Verbund Medizinischer Versorgungszentren:
Patientinnen und Patienten finden den passenden Standort, erhalten
Vorbereitungshinweise aus den Praxisdokumenten (mit Quellenangabe) und stellen
eine Terminanfrage – ohne dass das Sprachmodell ihre persönlichen Daten sieht.

**Das eigentliche Thema dieses Repos ist, wie es entstanden ist:** Der Mensch
hat Spezifikationen, Abnahmetests und Regeln geschrieben, Coding-Agenten haben
den Code geschrieben, ein Reviewer-Agent und die CI haben ihn geprüft.
→ [docs/factory.md](docs/factory.md)

> Alle Daten sind fiktiv. „MVZ Musterverbund Franken" ist ein erfundener Verbund.

## Was der Assistent kann

| Fähigkeit | Wie | Spec |
|---|---|---|
| Standorte nach Fachrichtung und Ort finden | Werkzeugaufruf auf das Standortverzeichnis | [002](specs/002-standort-suche.md) |
| Fragen zu Vorbereitung und Ablauf beantworten | RAG: lokale Embeddings, pgvector, lokales LLM, Quellenangabe | [003](specs/003-wissensbasis-rag.md), [004](specs/004-chat-assistent.md) |
| Freie Termine vorschlagen und anfragen | simuliertes Terminsystem, Formular statt Chat für personenbezogene Daten | [005](specs/005-terminanfrage.md) |
| Notfälle erkennen, keine medizinische Beratung | regelbasiert vor dem LLM, Leitplanken, Schutz vor Prompt-Injection | [006](specs/006-leitplanken.md) |
| Qualität messen | Eval mit 30 Fragen, Schwellenwerte blockieren die CI | [007](specs/007-evaluation.md) |
| Chat im Browser, auch mobil | React, barrierearm | [008](specs/008-chat-oberflaeche.md) |

## Schnellstart

Voraussetzungen: Docker, `make`, Python 3.12 (für die Robot-Tests) und für echte
Antworten [Ollama](https://ollama.com) mit `ollama pull qwen2.5:7b`. Das Modell
läuft lokal; keine Chat-Inhalte verlassen den Rechner.

```bash
cp .env.example .env          # für echte Antworten: LLM_PROVIDER=ollama (lokal) oder anthropic
make up                       # startet Datenbank, Backend, Frontend
make ingest                   # lädt die Wissensdokumente in die Vektordatenbank
open http://localhost:5173    # Chat
```

Tests:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r tests/acceptance/requirements.txt && rfbrowser init chromium
make acceptance               # Abnahmetests ohne echtes LLM (wie in der CI)
make acceptance-llm           # inkl. Tests gegen das echte LLM
make eval                     # Retrieval-Evaluation, Bericht in reports/eval/
```

`make lint` und `make test` laufen **lokal**, nicht im Container: Beim ersten
Aufruf legt das Makefile eine venv in `backend/.venv` an (Python 3.12,
`pip install -e "backend[dev]"`) und installiert die Frontend-Pakete mit
`npm ci`. Die pytest-Tests brauchen keine laufende Datenbank. Ein anderer
Python-Interpreter lässt sich mit `make test PYTHON=/pfad/zu/python3.12` wählen.

## Aufbau

```
specs/               Anforderungen und API-Verträge (Mensch)
tests/acceptance/    Abnahmetests in Robot Framework (Mensch, für Agenten gesperrt)
eval/fragen.yaml     Evaluationsfragen und Schwellenwerte (Mensch, gesperrt)
data/                fiktive Standorte und Patienteninformationen (Mensch)
CLAUDE.md, .claude/  Regeln, Befehle und Reviewer-Agent für Claude Code (Mensch)
backend/, frontend/  Anwendung (Agent)
docs/                Factory-Prozess, Factory-Log, Datenschutz
```

## Stand der Specs

| Spec | Titel | Status |
|---|---|---|
| 001 | Projektgerüst, lokale Umgebung und CI | fertig |
| 002 | Standortsuche | fertig |
| 003 | Wissensbasis und semantische Suche | fertig |
| 004 | Chat-Assistent mit Werkzeugen | fertig |
| 005 | Terminanfrage | fertig |
| 006 | Sicherheitsleitplanken | fertig |
| 007 | Evaluation | fertig |
| 008 | Chat-Oberfläche | offen |

## Datenschutz

Lokales, selbst betriebenes LLM (Ollama) und lokale Embeddings in der Demo,
Datenminimierung gegenüber dem LLM, Redaktion in Logs,
Löschfrist, Transparenzhinweis nach EU AI Act. Details und offene Punkte für
einen Produktivbetrieb: [docs/datenschutz.md](docs/datenschutz.md).

## Nächste Schritte

- Specs als GitHub Issues, Agent startet automatisch per GitHub Action
- Hybride Suche (Volltext + Vektor), falls die Eval es nahelegt
- Anbindung an ein echtes Terminsystem / PVS über die vorhandene Schnittstelle
- Betrieb auf Azure (Container Apps, Azure Database for PostgreSQL, Azure OpenAI in einer EU-Region)
- Mobile App (React Native) auf derselben API
