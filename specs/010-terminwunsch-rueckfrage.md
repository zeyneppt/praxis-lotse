# Spec 010 – Unvollständiger Terminwunsch: gezielte Rückfrage statt LLM

**Status:** fertig
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

**Ergänzung (Mensch):**

- (a) Kurze Nachrichten ohne Frageinhalt (höchstens 2 Wörter, kein Notfall, kein
  Terminwunsch, z. B. „ja", „ok", „danke", „nein") gehen nicht an das LLM. Feste Antwort
  aus `leitplanken/texte.py`: „Ich kann frühere Nachrichten nicht fortsetzen. Bitte stellen
  Sie Ihre Frage in einem ganzen Satz, zum Beispiel: „Termin Gastroenterologie in Fürth"
  oder „Was muss ich zum ersten Termin mitbringen?"" Bei „danke" ist eine freundliche
  Kurzantwort ok.
- (b) Markdown in LLM-Antworten serverseitig entfernen: `**fett**`/`__fett__` → Text,
  `[Text](URL)` → Text, Überschriften-`#` entfernen. Listen mit „- " dürfen bleiben.
  Die Oberfläche verlinkt Telefonnummern schon selbst.
- pytest für beides.

## Nicht im Umfang

- Den Verlauf auswerten (z. B. den zuletzt genannten Standort übernehmen)
- Umgangssprache ohne Fachrichtungsnamen („Frauenarzt", „Hausarzt")

## Umsetzungsnotizen

Plan:
1. `leitplanken/terminwunsch.py`: `erkenne_allgemeinen_terminwunsch()` – gleiche Wörter und
   Fachrichtungs-/Ort-/Standortregeln wie 009, dazu Wunschwort (`frei`/`buch`/`vereinbar`/`einen`)
   und Ausschlusswörter (`absag`/`verschieb`/`stornier`/`mitbring`); nur wenn 009 nicht greift.
2. Ergebnis: genau eine Fachrichtung (ohne Ort) oder Ort/Standort (ohne Fachrichtung), sonst Rückfrage.
3. Antworttexte in `leitplanken/texte.py`; ein Standort mit der Fachrichtung → Termine wie 009.
4. `run_chat`: Notfall → 009 → 010 → Kurznachricht (a) → LLM; Markdown-Bereinigung (b) der LLM-Antwort.
5. pytest: Erkennung (positiv/negativ/Ausschluss), alle Antwortfälle, (a), (b).
6. Container neu bauen (`LLM_PROVIDER=fake`), `make ingest`, `make lint`, `make test`,
   `make acceptance SPEC=010`, `make acceptance`.
7. Factory-Log, PR, CI mit `gh pr checks --watch` abwarten.

Entscheidungen (Details und offene Punkte im Factory-Log):
- Nur Standort genannt → Beispiel „Termin <Fachrichtung> im <Standortname>".
- Kurznachricht = höchstens 2 Wörter ohne Wort mit `termin`, Fachrichtung, Ort oder Standort
  (nach Review); „danke" (Wort mit `dank`) → freundliche Kurzantwort.
- Markdown-Entfernung nur für LLM-Antworten; bestehende pytest-Eingaben, die den
  LLM-Ablauf prüfen, auf ganze Sätze umgestellt.
- Ergebnis: pytest 484 grün, `make acceptance SPEC=010` 5/5, `make acceptance` 75/75.
