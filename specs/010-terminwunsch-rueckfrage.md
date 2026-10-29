# Spec 010 – Unvollständiger Terminwunsch: gezielte Rückfrage statt LLM

**Status:** offen
**Abhängigkeiten:** 009
**Abnahmetests:** `tests/acceptance/010_terminwunsch_rueckfrage.robot` (Tag `spec-010`)

## Ziel

Generalprobe mit `qwen2.5:7b` (29.10.2026, nach Spec 009): Nach Terminen im
MVZ Nürnberg Süd fragte die Person „Welche freien Termine gibt es bei Ihnen?".
Das Modell antwortete ohne Werkzeug, dort gebe es keine Termine für Innere
Medizin, und bot Allgemeinmedizin und Gynäkologie an – beides gibt es an
diesem Standort nicht. Keine Uhrzeit, also griff die Leitplanke aus Spec 009
nicht.

Ein Terminwunsch, dem Fachrichtung oder Ort fehlt, wird deshalb ebenfalls
**regelbasiert** beantwortet: mit einer Rückfrage, die nur echte Angaben aus
dem Standortverzeichnis enthält.

## Anforderungen

1. Ergänzung in `backend/app/leitplanken/terminwunsch.py` (gleiche
   Normalisierung und Wortregeln wie Spec 009). Reihenfolge im Chat:
   Notfall (006) → vollständiger Terminwunsch (009) → **allgemeiner
   Terminwunsch (010)** → bisheriger LLM-Ablauf.
2. **Allgemeiner Terminwunsch** liegt vor, wenn Spec 009 nicht greift und die Nachricht
   - ein Wort mit `termin` enthält (wie Spec 009, auch zusammengesetzt), **und**
   - einen Wunsch ausdrückt: ein Wort, das mit `frei`, `buch` oder `vereinbar`
     beginnt, oder das Wort `einen`, **und**
   - **kein** Wort enthält, das mit `absag`, `verschieb`, `stornier` oder
     `mitbring` beginnt (diese Fragen beantwortet die Wissensbasis).
3. **Antworten** (ohne LLM, `kategorie: "normal"`, Quelle
   `standorte.json`/„Standortverzeichnis"; Uhrzeiten nur über `aktion`):
   - **Genau eine Fachrichtung, kein Ort/Standort:**
     - Bietet sie im Verbund genau ein Standort an → Termine dieses Standorts
       wie in Spec 009 (`aktion` `termin_vorschlag`, Text nennt den Standort).
     - Mehrere Standorte → alle Standortnamen nennen, keine `aktion`,
       Beispiel „Termin <Fachrichtung> im <Standortname>".
   - **Ort oder Standort, keine Fachrichtung:** die Fachrichtungen nennen, die
     es dort gibt (nur diese), keine `aktion`, Beispiel
     „Termin <Fachrichtung> in <Ort>".
   - **Sonst** (nichts genannt oder mehrdeutig): Rückfrage nach Fachrichtung
     und Ort mit allen Fachrichtungen des Verbunds und dem Beispiel
     „Termin Gastroenterologie in Fürth". Keine `aktion`.
4. pytest für Erkennung (positiv, negativ, Ausschlusswörter) und alle Antwortfälle.
5. Das Chat-Limit (60/Minute) bleibt unverändert. Treten in `make acceptance`
   429-Fehler auf: Ursache im Factory-Log und im PR beschreiben und aufhören.
6. `docs/factory-log.md`: Eintrag mit Anlass (Generalprobe) und Ergebnis.

## Nicht im Umfang

- Den Verlauf auswerten (z. B. den zuletzt genannten Standort übernehmen)
- Umgangssprache ohne Fachrichtungsnamen („Frauenarzt", „Hausarzt")

## Umsetzungsnotizen

