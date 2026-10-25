# Spec 007 – Evaluation der Antwortqualität

**Status:** offen
**Abhängigkeiten:** 003, 004, 006
**Abnahmetests:** `tests/acceptance/007_eval.robot` (Tag `spec-007`)

## Ziel

Die Qualität des Assistenten wird gemessen statt geschätzt. Jede Änderung an
Prompt, Chunking oder Modell zeigt sofort, ob es besser oder schlechter wird.

## Anforderungen

1. CLI `python -m app.eval` im Backend, aufgerufen über `make eval` mit
   `docker compose exec -T --user "$(id -u):$(id -g)" backend …`, damit die
   Berichte auf dem Host der aufrufenden Person gehören.
   Liest `eval/fragen.yaml` (Pfad über `EVAL_DATEI`, im Container nach
   `/eval/fragen.yaml` gemountet).
2. **Modus `retrieval`** (Standard, ohne LLM, läuft in CI):
   - `wissen`: Treffer, wenn `erwartete_quelle` unter den Top 3 von
     `/api/wissen/suche` ist. Kennzahl `retrieval_treffer_top3` = Anteil Treffer.
   - `notfall`: `POST /api/chat` muss `kategorie: "notfall"` liefern und alle
     Begriffe aus `muss_enthalten` enthalten. Kennzahl `notfall_erkennung`.
3. **Modus `voll`** (`make eval MODUS=voll`, braucht `LLM_PROVIDER=ollama` oder `anthropic`):
   zusätzlich `wissen`/`standort`: Antwort enthält alle `muss_enthalten`;
   `grenze`: Antwort enthält nichts aus `darf_nicht_enthalten`.
   Kennzahlen `antwort_korrekt` und `grenzen_eingehalten`.
   Im Modus `voll` enthält das Ergebnis zusätzlich `llm_provider` und
   `llm_model`, damit Läufe mit verschiedenen Modellen vergleichbar sind.
4. **Ergebnis:** schreibt auf dem Host (Volume-Mount `./reports`) die Dateien
   `reports/eval/ergebnis.json` und
   `reports/eval/ergebnis.md` (Tabelle pro Frage: id, typ, bestanden, Details,
   darunter Kennzahlen). Gibt die Kennzahlen auch auf der Konsole aus.
5. **Schwellenwerte** aus `schwellenwerte` in `fragen.yaml`. Unterschreitet
   eine Kennzahl ihren Schwellenwert, endet der Befehl mit Exit-Code 1.
   Damit blockiert die CI Verschlechterungen.
6. CI-Job `eval` aus Spec 001 wird aktiviert und lädt `reports/eval/` als Artefakt hoch.

## Format `reports/eval/ergebnis.json`

```json
{
  "modus": "retrieval",
  "zeitpunkt": "2026-10-30T10:00:00+01:00",
  "kennzahlen": {"retrieval_treffer_top3": 0.952, "notfall_erkennung": 1.0},
  "bestanden": true,
  "fragen": [{"id": "w01", "typ": "wissen", "bestanden": true, "details": "Rang 1"}]
}
```

## Nicht im Umfang

- LLM-as-a-Judge (eine spätere Spec, wenn Stichwortvergleiche nicht mehr reichen)

## Umsetzungsnotizen

