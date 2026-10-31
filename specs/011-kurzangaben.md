# Spec 011 – Kurzangaben wie „Kardiologie Fürth" als Terminwunsch

**Status:** fertig
**Abhängigkeiten:** 009, 010
**Abnahmetests:** `tests/acceptance/011_kurzangaben.robot` (Tag `spec-011`)

## Ziel

Auf die Rückfrage aus Spec 010 („Für welche Fachrichtung und an welchem Ort …?")
antworten Menschen knapp: „Kardiologie Fürth" oder „Neurologie bitte" – ohne
das Wort „Termin". Solche Nachrichten gehen bisher an das LLM, also genau in
die Lage aus der Generalprobe, in der das Modell Angebote erfunden hat
(Review-Hinweis zu Spec 010).

Eine Nachricht, die **nur** aus einer Fachrichtung, optional Ort/Standort und
Füllwörtern besteht, wird deshalb wie ein Terminwunsch behandelt.

## Anforderungen

1. Ergänzung in `backend/app/leitplanken/terminwunsch.py`, gleiche
   Normalisierung und Wortregeln wie Spec 009/010.
2. **Kurzangabe** liegt vor, wenn
   - die Nachricht **genau eine Fachrichtung** nennt (Regeln aus Spec 009), **und**
   - **jedes** Wort der Nachricht zu einer der folgenden Gruppen gehört:
     Wörter der genannten Fachrichtung, eines genannten Orts oder Standortnamens,
     oder Füllwörter: `in`, `im`, `bei`, `beim`, `der`, `die`, `das`, `den`,
     `dem`, `am`, `an`, `für`, `zur`, `zum`, `und`, `mvz`, `bitte`, `gern`,
     `gerne`, `ja`, `eher`, `lieber`.
   Satzzeichen zählen nicht als Wörter.
3. Eine Kurzangabe wird beantwortet **wie ein Terminwunsch mit denselben
   Angaben** (Spec 009 mit Ort/Standort, Spec 010 ohne Ort) – ohne LLM, mit
   denselben Texten, Quellen und `aktion`.
4. Reihenfolge: Notfall → Spec 009 → Spec 010 → **Kurzangabe (011)** →
   Kurznachricht (010, Ergänzung) → LLM.
5. Enthält die Nachricht ein weiteres Wort (z. B. „Öffnungszeiten der
   Kardiologie in Schwabach?"), ist es keine Kurzangabe; der bisherige Ablauf
   bleibt unverändert.
6. pytest: positive und negative Beispiele, auch mit Satzzeichen und
   Groß-/Kleinschreibung.
7. Das Chat-Limit (60/Minute) bleibt unverändert. Treten in `make acceptance`
   429-Fehler auf: Ursache im Factory-Log und im PR beschreiben und aufhören.
8. `docs/factory-log.md`: Eintrag mit Anlass und Ergebnis; README-Tabellen
   („Was der Assistent kann", „Stand der Specs") um 011 ergänzen.

## Nicht im Umfang

- Verlauf auswerten (z. B. „ja" als Zustimmung zur vorigen Rückfrage)
- Nur ein Ort ohne Fachrichtung („Fürth") – bleibt beim LLM mit Standortsuche

## Umsetzungsnotizen

Plan:
1. `leitplanken/terminwunsch.py`: Erkennung von Ort/Standort aus Spec 009 in eine Hilfsfunktion
   ohne „Termin"-Prüfung auslagern; 009 und 010 nutzen sie unverändert weiter.
2. `erkenne_kurzangabe()`: genau eine Fachrichtung (Regeln 009); jedes Wort ist ein Wort der
   Fachrichtung (Präfixregel), des erkannten Orts/Standortnamens oder ein Füllwort der Spec.
3. Ergebnis wie ein Terminwunsch mit denselben Angaben: mit eindeutigem Ort/Standort →
   `Terminwunsch` (Antwort 009); ohne Ort → `AllgemeinerTerminwunsch(fachrichtung=…)`
   (Antwort 010); mehrdeutig (zwei Orte/Standorte) → Rückfrage wie 010.
4. `run_chat`: Notfall → 009 → 010 → Kurzangabe → Kurznachricht → LLM; keine neuen Texte.
5. pytest: positive/negative Beispiele (Satzzeichen, Groß-/Kleinschreibung), Chat-Antworten ohne LLM.
6. Container neu bauen (`LLM_PROVIDER=fake`), `make ingest`, `make lint`, `make test`,
   `make acceptance SPEC=011`, dann `make acceptance`.
7. README-Tabellen und Factory-Log ergänzen.

Ergebnis: lint ok, pytest 546, `make acceptance SPEC=011` 5/5, `make acceptance` 80/80 (ohne 429).
