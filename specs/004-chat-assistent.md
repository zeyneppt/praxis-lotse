# Spec 004 – Chat-Assistent mit Werkzeugen

**Status:** offen
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

