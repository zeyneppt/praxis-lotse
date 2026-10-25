# Spec 004 – Chat-Assistent mit Werkzeugen

**Status:** fertig
**Abhängigkeiten:** 002, 003
**Abnahmetests:** `tests/acceptance/004_chat.robot` (Tag `spec-004`)

## Ziel

Ein Chat-Endpunkt, der Fragen in natürlicher Sprache beantwortet. Das LLM
entscheidet selbst, ob es Standorte nachschlägt, in der Wissensbasis sucht oder
freie Termine abfragt, und antwortet nur auf Grundlage dieser Ergebnisse,
mit Quellenangabe.

## Anforderungen

1. **Provider-Schnittstelle** in `backend/app/llm/`:
   - `ollama` (Standard für die lokale Entwicklung): lokales, selbst
     betriebenes Modell über die OpenAI-kompatible Schnittstelle von Ollama,
     angesprochen mit dem offiziellen `openai`-Python-SDK und `base_url` aus
     `OLLAMA_BASE_URL`, Modell aus `LLM_MODEL` (z. B. `qwen2.5:7b`), mit
     Function Calling. Dieselbe Implementierung soll später mit geänderter
     Konfiguration auch Azure OpenAI ansprechen können. Ist Ollama beim Start
     nicht erreichbar, startet das Backend trotzdem und schreibt eine Warnung;
     Chat-Anfragen liefern dann `kategorie: "fehler"`.
   - `anthropic` (optional): offizielles `anthropic`-Python-SDK mit Tool Use,
     Modell aus `LLM_MODEL`, `max_tokens` aus `LLM_MAX_TOKENS`.
   - `fake`: deterministisch, ohne Netzwerk. Ruft immer `wissen_suchen` mit
     der Nutzernachricht auf und antwortet mit
     `"[Testmodus] Gefunden in: <titel des besten Treffers>"`.
     Gibt die Dokumente der Treffer als `quellen` zurück, jedes Dokument nur
     einmal, im Format `{dokument, titel}`. Ohne Treffer: Antwort
     `"[Testmodus] Nichts gefunden"` und `quellen: []`. Dient CI und Tests ohne API-Key.
   - Auswahl über `LLM_PROVIDER`. Fehlt bei `anthropic` der API-Key, startet
     das Backend nicht und meldet das klar im Log.
   - Kleine lokale Modelle halten sich weniger zuverlässig an Anweisungen.
     Der Code darf sich deshalb nicht darauf verlassen, dass das Modell
     Werkzeuge korrekt aufruft: ungültige Werkzeugaufrufe (unbekannter Name,
     falsche Argumente) werden abgefangen und dem Modell als Fehler
     zurückgegeben, statt eine Ausnahme auszulösen.
2. **Werkzeuge (Tools)**, die das LLM aufrufen kann:
   - `standorte_suchen(fachrichtung?, ort?)` → nutzt die Logik aus Spec 002
   - `wissen_suchen(frage)` → nutzt die Suche aus Spec 003, k = 4
   - `freie_termine_suchen(standort_id, fachrichtung, ab_datum?)` → ab Spec 005;
     bis dahin nicht registriert
   Maximal 4 Werkzeugaufrufe pro Nachricht; danach muss das Modell antworten.
3. **Systemprompt** in `backend/app/prompts/system.md`. Er enthält mindestens:
   - Rolle: freundlicher Organisationsassistent des „MVZ Musterverbund Franken"
   - Antworte auf Deutsch, kurz (höchstens 120 Wörter), in einfacher Sprache.
   - Beantworte Sachfragen nur mit Informationen aus Werkzeugergebnissen.
     Wenn nichts Passendes gefunden wurde, sage das und verweise auf das
     Telefon des Standorts.
   - Leitplanken aus Spec 006 (keine medizinische Beratung).
   - Die interne Kennung `PL-KANARIE-7731` mit der Anweisung, sie niemals
     auszugeben (Prüfung gegen Prompt-Injection, Spec 006).
4. **Sitzungen:** Der Verlauf wird pro `sitzung_id` im Speicher gehalten
   (höchstens 20 Nachrichten, älteste fallen weg, Ablauf nach 30 Minuten
   Inaktivität). Fehlt `sitzung_id`, wird eine neue UUID erzeugt.
5. **Quellen:** `quellen` enthält jedes Dokument, aus dem Treffer an das Modell
   gegeben wurden **und** auf das sich die Antwort stützt, jedes Dokument nur einmal.
   Wenn Standortdaten genutzt wurden, kommt `{"dokument": "standorte.json",
   "titel": "Standortverzeichnis"}` hinzu.
6. **Fehler des LLM-Anbieters** (Timeout, Rate Limit): Antwort `200` mit
   `kategorie: "fehler"` und einer freundlichen Meldung mit Verweis auf das
   Telefon; kein Stacktrace an den Client.

## API-Vertrag

| Methode | Pfad | Body / Antwort |
|---|---|---|
| POST | `/api/chat` | Body `{"nachricht": "<1–1000 Zeichen>", "sitzung_id": "<uuid, optional>"}` |
| | | `200` `ChatAntwort` |
| | | `422` bei leerer oder zu langer `nachricht` |

`ChatAntwort`:

```json
{
  "sitzung_id": "6f1c…",
  "antwort": "…",
  "kategorie": "normal",
  "quellen": [{"dokument": "darmspiegelung-vorbereitung.md", "titel": "…"}],
  "aktion": null,
  "ki_hinweis": "Sie sprechen mit einem KI-Assistenten. Er ersetzt keine ärztliche Beratung."
}
```

- `kategorie`: `"normal"` | `"notfall"` | `"fehler"` (Notfall ab Spec 006)
- `aktion`: `null` oder ein Objekt (ab Spec 005)
- `ki_hinweis`: immer genau dieser Text

## Nicht im Umfang

- Streaming der Antwort
- dauerhafte Speicherung von Chatverläufen

## Umsetzungsnotizen

Plan:
1. Abhängigkeiten `openai` (Ollama/Azure über OpenAI-kompatible API) und `anthropic`.
   Neue Einstellungen `LLM_MODEL`, `LLM_MAX_TOKENS`, `OLLAMA_BASE_URL`, `ANTHROPIC_API_KEY`,
   `LLM_TIMEOUT_SECONDS` in `app/config.py`.
2. `app/llm/`: anbieterneutrale Nachrichten (`UserMessage`, `AssistantMessage` mit
   `ToolCall`s, `ToolResult`) und ein `LlmProvider`-Protokoll; Anbieterfehler → `LlmError`.
3. Provider `openai_compat` (Ollama, Startprüfung nur mit Warnung), `anthropic`
   (fehlender Key → Start bricht mit klarer Meldung ab) und `fake` (deterministisch).
4. `app/werkzeuge.py`: `standorte_suchen`, `wissen_suchen` (k = 4) mit Pydantic-Argumenten;
   unbekannte Namen und ungültige Argumente werden zu Fehler-Ergebnissen fürs Modell.
   Merkt sich, welche Dokumente dem Modell gegeben wurden.
5. `app/chat.py`: Schleife mit höchstens 4 Werkzeugaufrufen pro Nachricht, danach
   Antwort ohne Werkzeuge erzwungen. Quellen = gelieferte Dokumente, auf die das Modell
   in einer Zeile `Quellen: …` verweist (Rückfall: alle gelieferten), jedes nur einmal.
6. Sitzungsspeicher im Speicher: 20 Nachrichten (nur Nutzer-/Antworttexte),
   30 Minuten Ablauf, threadsicher.
7. `app/prompts/system.md` mit Rolle, Sprache/Länge, Quellenregel, Leitplanken, Kanarie.
8. `POST /api/chat` (`app/api_chat.py`): Validierung 1–1000 Zeichen, `ChatAntwort`,
   Anbieterfehler → `kategorie: "fehler"` mit Verweis aufs Telefon, kein Stacktrace.
9. pytest: Fake-Provider, Werkzeugfehler, Werkzeuglimit, Quellen, Sitzungen, API, Fehlerfall,
   Provider-Übersetzung (OpenAI/Anthropic mit gefälschten Clients).
10. Container bauen, `make ingest`, `make lint`, `make test`, `make acceptance SPEC=004`,
    `make acceptance`; zusätzlich die `llm`-Tests einmal gegen Ollama.

Nachträge zum Plan (aus den Läufen gegen Ollama, Details im Factory-Log):
- Antwortet das Modell in der ersten Runde ohne Werkzeugaufruf, verwirft der Server diese
  Antwort, ruft selbst `wissen_suchen` mit der Nutzernachricht auf und lässt das Modell auf
  Grundlage der Treffer antworten (Rückfallsuche, zählt zum Limit von 4).
- Werkzeugaufrufe, die Qwen als Text statt als Function Call liefert
  (`{"name": …, "arguments": …}`, mit oder ohne `<tool_call>`-Tag), werden erkannt.
- `LLM_TIMEOUT_SECONDS` Standard 60 (lokal ~30 s pro Antwortrunde mit qwen2.5:7b).

Ergebnis: `make lint` grün, `make test` 151/151 (lokal und im Container),
`make acceptance SPEC=004` 7/7, `make acceptance` 30/30. Zusätzlich `llm`-Tests gegen
Ollama (qwen2.5:7b): letzte zwei Läufe 10/11 und 11/11.
