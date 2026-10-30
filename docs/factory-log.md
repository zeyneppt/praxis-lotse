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

## Spec 010 – Unvollständiger Terminwunsch: Rückfrage statt LLM (2026-10-29)

- Anlass: Generalprobe mit `qwen2.5:7b` nach Spec 009 – auf „Welche freien Termine gibt es
  bei Ihnen?" bot das Modell ohne Werkzeug Fachrichtungen an, die es am zuvor genannten
  Standort (MVZ Nürnberg Süd) nicht gibt.
- Ergebnis: Terminwünsche ohne Fachrichtung oder Ort beantwortet der Server ohne LLM, nur mit
  Angaben aus `standorte.json`. Reihenfolge: Notfall → 009 → 010 → Kurznachricht → LLM.
  Dazu die Ergänzungen des Menschen: (a) Kurznachrichten (≤ 2 Wörter) bekommen eine feste
  Antwort, „danke" eine freundliche Kurzantwort; (b) Fettdruck, Links und Überschriften-`#`
  werden aus LLM-Antworten entfernt.
- Durchläufe bis alle Tests grün: 4 pytest-, 4 lint-Läufe; Abnahmetests beim 1. Lauf grün.
  Am Ende: lint ok, pytest 471, `make acceptance SPEC=010` 5/5, `make acceptance` 75/75
  ohne 429, `make eval` Retrieval 0.952 / Notfall 1.0. Alles mit `LLM_PROVIDER=fake`,
  ohne Ollama (Vorgabe des Menschen); `make acceptance-llm` deshalb nicht gelaufen.
- Fehler des Agenten und wie sie erkannt wurden:
  - Zwei eigene Testerwartungen waren falsch (pytest): „Lauf" ist der Kurzname von „MVZ Lauf"
    und zählt wie in 009 als Standort, nicht als Ort; „Terminbuchung" beginnt nicht mit
    `buch`, ist also nach Anforderung 2 kein Wunschwort. Tests korrigiert, nicht der Code.
  - Die Kurznachrichten-Regel hat 12 bestehende pytest-Tests getroffen, die den LLM-Ablauf
    mit Eingaben wie „Hallo", „Frage" oder „Akupunktur?" prüfen. Eingaben in ganze Sätze
    geändert, Prüfungen unverändert. Ebenso `test_erfundene_uhrzeit_wird_ersetzt` (009):
    „Ich hätte gern einen Termin beim Hausarzt" ist jetzt ein allgemeiner Terminwunsch, die
    Eingabe heißt dort jetzt „Ich hätte gern Termine beim Hausarzt".
  - mypy: fehlende Typargumente in den neuen Tests, ruff: Zeilenlänge/Importreihenfolge.
- Getroffene Annahmen:
  - Nur ein Standort genannt (ohne Fachrichtung): Das Beispiel lautet „Termin <Fachrichtung>
    im <Standortname>" statt „… in <Ort>", weil „in Nürnberg" wieder mehrdeutig wäre.
  - Beispiel-Fachrichtung bzw. -Standort ist jeweils der erste der Liste (alphabetisch
    bzw. in Verzeichnisreihenfolge).
  - Eine Fachrichtung mit unbekanntem Ort („Termin Kardiologie in München") gilt als „nur
    Fachrichtung"; der Text nennt den Standort, an dem es sie gibt.
  - Kurznachricht = höchstens 2 Wörter ohne Wort mit `termin`, Fachrichtung, Ort oder
    Standort (seit Review-Runde 1). „danke" = ein Wort, das mit `dank` beginnt („Vielen Dank").
  - Markdown-Entfernung nur im LLM-Ablauf, nach dem Abtrennen der Quellenzeile; Listen und
    `*`-Aufzählungen bleiben.
- Offene Punkte:
  - „Hallo" bekommt jetzt die Kurznachricht-Antwort („Ich kann frühere Nachrichten nicht
    fortsetzen …"); für eine Begrüßung klingt das schief. Ggf. eigene Antwort für Grüße.
  - „Hilfe!" und „Notruf" erkennt die Notfall-Erkennung (006) nicht; sie bekommen jetzt die
    feste Kurznachricht-Antwort ohne 112-Hinweis (Review-Runde 2). Entscheidung Mensch:
    Notfallwörter ergänzen oder 112/116117 in den festen Text.
  - „Ja, bitte" auf eine Rückfrage bekommt ebenfalls die feste Antwort (bewusst, Verlauf
    nicht im Umfang). „Kardiologie Fürth" ohne „Termin" nach der Rückfrage geht weiter an
    das LLM – Kandidat für eine Folge-Spec.
  - Ausschluss- und Wunschwörter gelten nur am Wortanfang: „Terminbuchung" oder
    „Terminabsage" werden nicht als Wunsch- bzw. Ausschlusswort erkannt.
  - `make acceptance-llm` und `make eval MODUS=voll` nicht gelaufen (kein Ollama).
- Review Runde 1 (Subagent `reviewer`), 2 blockierende Punkte:
  - Kurznachricht-Regel zu breit: „Termin absagen", „Termin Kardiologie", „Öffnungszeiten
    Fürth?" bekamen die feste Antwort statt Wissensbasis/LLM – ein Rückschritt, den ich nur
    als offenen Punkt notiert und trotzdem `fertig` gesetzt hatte. Behoben: Kurznachricht nur
    ohne Wort mit `termin` und ohne Fachrichtung, Ort oder Standort (`nennt_angaben()`);
    pytest-Fälle dafür ergänzt. „Hallo" bekommt weiterhin die feste Antwort.
  - „Ergänzung (Mensch)" in der Spec: Wortlaut vom Menschen in dieser Sitzung vorgegeben
    (Auftrag zu Spec 010), vom Agenten eingetragen; Bestätigung im PR erbeten.
  - Hinweise umgesetzt: `__init__.py` bleibt unverändert, Links mit Klammern in der URL
    werden vollständig entfernt (je ein pytest-Fall). Ein Fehlversuch: `(?![\w.])` hätte
    „__wichtig__." nicht mehr entfernt, jetzt `(?!\.?\w)`.
  - Nach den Korrekturen: lint ok, pytest 484, `make acceptance SPEC=010` 5/5,
    `make acceptance` 75/75.
- Review Runde 2: freigegeben, keine blockierenden Punkte (Hinweise oben unter „Offene Punkte").

## Spec 009 – Terminwunsch regelbasiert erkennen (2026-10-29)

- Anlass: Generalprobe mit `qwen2.5:7b` – bei „Termin in der Gastroenterologie in Fürth"
  kein Aufruf von `freie_termine_suchen`, einmal Wissenstext, einmal erfundene Termine.
- Ergebnis: Eindeutige Terminwünsche (Termin + genau eine Fachrichtung + genau ein Ort)
  beantwortet jetzt der Server ohne LLM; Termine kommen nur aus dem Terminsystem.
  Im LLM-Ablauf ersetzt eine Leitplanke Antworten mit Uhrzeit, wenn das Terminsystem
  keine Termine geliefert hat.
- Durchläufe bis alle Tests grün: 1 (lint, pytest 366, `make acceptance SPEC=009` 9/9,
  `make acceptance` 70/70 ohne 429, `make eval` Retrieval 0.952 / Notfall 1.0).
- Fehler des Agenten und wie sie erkannt wurden:
  - Eine angefangene, unbenutzte Hilfsfunktion im neuen Modul noch vor dem ersten Lauf
    beim Durchlesen entfernt. Sonst keine.
- Getroffene Annahmen:
  - „einen Ort": Nennt die Nachricht **zwei** Orte (z. B. „Stein oder Feucht"), ist der
    Wunsch nicht eindeutig → bisheriger LLM-Ablauf. Analog zu „genau einer Fachrichtung".
  - Mehrwort-Fachrichtungen: Jedes Wort der Folge darf gebeugt sein (Präfixvergleich),
    damit „in der Inneren Medizin" erkannt wird – dieselbe Regel wie bei Einwortnamen.
  - „`freie_termine_suchen` nicht erfolgreich aufgerufen" = das Terminsystem hat keinen
    Termin geliefert (Fehler **oder** leere Liste). Uhrzeiten nach einer leeren Liste
    wären ebenso erfunden.
  - Antworttexte der vier Fälle stehen wie die Leitplanken-Texte in `leitplanken/texte.py`.
    Formulierung „freie Termine für <Fachrichtung> im <Standort>" statt „in der …",
    weil „in der Innere Medizin" grammatisch nicht passt.
  - Keine freien Termine: Antwort nennt die Telefonnummer des Standorts.
  - Die `aktion` kommt jetzt aus `ChatErgebnis.termin_vorschlag` statt direkt aus dem
    `Werkzeugkasten`; Verhalten im LLM-Ablauf unverändert.
- Nicht ausgeführt:
  - `make acceptance-llm` und `make eval MODUS=voll` – Vorgabe des Menschen für diesen
    Lauf: `LLM_PROVIDER=fake`, kein Ollama.
- Akzeptierte Grenzen (vom Menschen nach dem Review so entschieden):
  - Orte, die auch Alltagswörter sind („Stein", „Lauf", „Feucht"), können in seltenen
    Sätzen falsch als Ort gelten („Termin wegen Nierenstein" trifft nicht, „ein Stein" schon).
    Folge: falscher Standortvorschlag, aber keine erfundenen Termine.
  - Die Uhrzeit-Leitplanke ersetzt auch korrekte Öffnungszeiten („ab 08:00"), wenn die
    Frage „Termin" enthält und kein Termin geliefert wurde.
  - Ein Datum wie „02.11." zählt als Uhrzeit (Muster aus der Spec) – bewusst so belassen.
- Eingriffe durch den Menschen:
  - Lauf ohne Ollama; CI nach dem Push abwarten, nicht mergen.
  - Nach dem Review vier Punkte im selben PR (siehe Nachtrag).
- Review-Ergebnis: freigegeben nach 1 Runde, keine blockierenden Punkte.

### Nachtrag nach Review – Spec 009 (2026-10-29)

- Vorgaben des Menschen:
  1. **Ergänzung (Mensch) in der Spec:** Ein genannter Standortname (voll oder ohne „MVZ ")
     hat Vorrang vor dem Ort. Die Auswahlantwort nennt ein Beispiel. Damit ist der offene
     Punkt „Auswahl bei mehreren Standorten führt wieder zur Auswahl" erledigt.
  2. „termin" auch in zusammengesetzten Wörtern („Untersuchungstermin", „Wunschtermin"),
     für Erkennung und Uhrzeit-Leitplanke; Uhrzeit-Muster ohne Groß-/Kleinschreibung.
  3. Terminsystem-Ausfall → freundliche Antwort mit `kategorie: "fehler"` statt 500.
  4. Leere Terminliste im LLM-Ablauf → keine `aktion`.
- Durchläufe bis alle Tests grün: 1 (pytest 394, `make acceptance` 70/70 ohne 429,
  `make eval` Retrieval 0.952 / Notfall 1.0). Vorher zwei kleine Fehler:
  - Ein Ersetzungsskript fand eine Zeile nicht, weil `ruff format` die Bedingung auf eine
    Zeile gezogen hatte; nur die übrigen Dateien waren geschrieben – erkannt an der
    Fehlermeldung, Rest gezielt nachgezogen.
  - `ruff` bemängelte die Importreihenfolge des neuen `TerminsystemNichtErreichbar`.
- Getroffene Annahmen:
  - Der Kurzname ohne „MVZ " zählt nur, wenn er nicht selbst ein Ort ist: „Erlangen" ist
    der Ort Erlangen (mit beiden Standorten), „MVZ Erlangen" der Standort std-009.
    Sonst würde „Termin Gynäkologie in Erlangen" am MVZ Erlangen scheitern, obwohl das
    MVZ Erlangen Süd sie anbietet.
  - Steckt eine Nennung in einer längeren („MVZ Erlangen" in „MVZ Erlangen Süd"), zählt
    nur die längere. Zwei verschiedene Standorte genannt → nicht eindeutig → LLM-Ablauf.
  - Mit Standortnamen ist der Ort durch den Standort festgelegt; ein zusätzlich genannter
    anderer Ort wird ignoriert („MVZ Stein, nicht in Feucht" → std-006).
  - Eigener Text für „Standort hat die Fachrichtung nicht": „Im <Standort> gibt es keine
    <Fachrichtung>. … gibt es im Verbund hier: …".
  - Das Beispiel in der Auswahlantwort nennt den ersten passenden Standort.
  - Ausfall: Das simulierte Terminsystem übersetzt `SQLAlchemyError` beim Lesen freier
    Termine in `TerminsystemNichtErreichbar`. `/api/chat` fängt das für beide Wege
    (Regel und Werkzeug) ab und loggt nur den Fehlertyp. Die Sitzung speichert in dem
    Fall nichts, wie beim LLM-Ausfall. Andere Endpunkte (`/api/termine/...`) unverändert.
  - „termin" als Teilwort trifft theoretisch auch „determiniert" o. Ä.; im Praxis-Chat
    vernachlässigbar.

## Spec 008 – Chat-Oberfläche (2026-10-27)

- Durchläufe bis alle Tests grün: 1 (`make lint` 1, `make acceptance SPEC=008` 6/6 im ersten Lauf);
  `make acceptance` (alle Specs, ohne `llm`) 61/61 – erstmals einschließlich Spec 001 „Frontend zeigt die Überschrift",
  weil die Browser Library jetzt in `.venv` installiert ist (`pip install -r tests/acceptance/requirements.txt`, `rfbrowser init chromium`).
- `llm`-Test „Terminanfrage über das Formular" nicht ausgeführt: `LLM_PROVIDER=fake` auf Anweisung, Ollama nicht gestartet.
  Der `fake`-Provider erzeugt nie eine `aktion`. Ersatzprüfung (nicht eingecheckt): Playwright-Skript mit gemocktem
  `/api/chat` (`termin_vorschlag` mit echtem Slot) und echtem `POST /api/termine/anfragen` → Bestätigung mit Datum,
  Uhrzeit und „MVZ Fürth Zentrum"; zweite Anfrage desselben Slots → Hinweis „schon vergeben" (409); `scrollWidth` 375.
  Dabei wurde lokal ein Slot (std-004, 28.10.2026 08:30) in der Entwicklungsdatenbank angefragt.
- Fehler des Agenten und wie sie erkannt wurden:
  - Erstes `pattern` für das Telefonfeld (`[0-9 +/\-]`) wäre im `v`-Modus moderner Browser ungültig gewesen (unescaptes `/`)
    und damit still ignoriert worden – beim Durchlesen bemerkt, vor dem ersten Testlauf korrigiert.
  - Ersatzprüfung lief zuerst nicht: Playwright fand Chromium nicht, weil `rfbrowser` die Browser im Paket ablegt
    (`PLAYWRIGHT_BROWSERS_PATH=0`).
- Getroffene Annahmen:
  - Keine pytest-Tests: Die Spec ändert nur das Frontend. Ein Frontend-Testframework (z. B. Vitest) wäre eine neue
    Abhängigkeit, die die Spec nicht verlangt. Die Logik liegt in reinen Funktionen (`src/format.ts`), damit sie später testbar ist.
  - Telefonnummern werden in **allen** Assistenten-Nachrichten verlinkt (112, 116117, Nummern mit `0…`/`+49…`), nicht nur bei Notfällen –
    Fehler- und Normalantworten verweisen ebenfalls auf das Praxistelefon. Nebenwirkung: Eine frei stehende „112" in anderem Sinn würde auch verlinkt.
  - Der KI-Hinweis steht im festen Kopfbereich; nur der Verlauf scrollt (so bleibt er „dauerhaft sichtbar").
  - Die Begrüßung ist normaler Text (kein `nachricht-assistent`) und enthält einen `tel:112`-Link.
  - Netzwerkfehler, Zeitüberschreitung (90 s) und HTTP-Fehler beim Chat erscheinen als Fehlermeldung (`role="alert"`) unter dem Verlauf,
    nicht als Assistenten-Nachricht; `429` bekommt einen eigenen Text.
  - Formular: Browser-Validierung (`required`, `minLength`, `pattern`, Datum ≤ heute) vor dem Senden; der Server bleibt maßgeblich, `422` → Hinweis „Angaben prüfen".
    Formulardaten liegen nur im Komponentenzustand und werden nach Erfolg verworfen; kein `console.log`.
  - Termin-Zeiten werden in `Europe/Berlin` angezeigt, unabhängig von der Zeitzone des Geräts.
  - Senden-Knopf ist nur während einer laufenden Anfrage deaktiviert; leere Eingaben werden ignoriert.
  - Kontrast der Farben nach WCAG-Formel gewählt, aber nicht mit einem Werkzeug (z. B. axe) gemessen.
- Offene Punkte:
  - Kein Dark Mode.
  - `make acceptance-llm` (mit Ollama) steht noch aus – vom Menschen auszuführen.
  - Ein automatisierter Barrierefreiheits-Check (axe) wäre eine sinnvolle Ergänzung der Abnahmetests.
- Eingriffe durch den Menschen:
  - Anweisung: `LLM_PROVIDER=fake`, `llm`-Test nicht ausführen, Browser Library lokal in `.venv` installieren, CI nach dem Push abwarten, nicht mergen.
- Review-Ergebnis: freigegeben nach 1 Runde (keine blockierenden Punkte, 9 Hinweise im PR-Kommentar).
- Nachbesserung nach Review (auf Anweisung des Menschen, ohne neue Abhängigkeit):
  - Telefon-Links: nur 112, 116117 und Nummern mit `+49` oder Vorwahl (`0` + mind. zwei Ziffern) mit mind. 6 Ziffern;
    Bindestrich nur ohne Leerzeichen als Trenner. „08 - 12 Uhr", „08:00-12:00", „03/2026", „01067 Dresden" werden nicht mehr verlinkt.
  - Fokusrahmen `#083d6d` (≥ 9:1 auf allen verwendeten Hintergründen, statt ca. 2:1).
  - Eine einzige Live-Region (`aria-live="polite"`, unsichtbar) sagt jede Antwort an, Notfälle mit „Notfall:"; `role="alert"` an der
    Notfall-Nachricht und `aria-live` am Verlauf entfernt. Status/Alert im Terminformular liegen damit nicht mehr in einer Live-Region.
  - Formular wie der Server: Geburtsdatum höchstens gestern in `Europe/Berlin`; Telefon-`pattern` verlangt mind. 6 Ziffern.
  - Nach `409` ist der Slot deaktiviert („Bereits vergeben"), Absenden gesperrt; beim Wechsel auf einen anderen Slot
    bleiben die eingegebenen Daten erhalten (Formular nicht mehr per `key` an den Slot gebunden).
  - Unit-Tests für `format.ts` mit dem eingebauten `node:test` (Node ≥ 22.18 entfernt TypeScript-Typen selbst), Aufruf über
    `npm test` und `make test`. Die Testdatei ist von `tsc` ausgenommen, weil `@types/node` fehlt; sie wird also nicht typgeprüft.
  - Durchläufe: `node --test` 7/7 im ersten Lauf, `make lint` grün, `make test` 327 + 7, `make acceptance` 61/61.
  - Fehler des Agenten: Im eigenen Browser-Prüfskript wurden die Links gelesen, bevor die Antwort da war (leere Liste) –
    kein Codefehler, Skript wartet jetzt auf die Nachricht. Bei den Prüfungen wurden lokal weitere Slots in der Entwicklungs-DB angefragt.

## Spec 007 – Evaluation der Antwortqualität (2026-10-27)

- Durchläufe bis alle Tests grün: pytest 2 Läufe (erster: ruff E501/Format in den neuen Dateien),
  `make eval` 1 Lauf, `make acceptance SPEC=007` 1 Lauf (2/2). `make acceptance` (alle Specs, ohne `llm`):
  54/55; fehlgeschlagen ist nur Spec 001 „Frontend zeigt die Überschrift" (Browser Library fehlt in meiner
  Test-Umgebung, wie schon bei Spec 006), kein Codefehler.
- `llm`-Tests und echte Messung im Modus `voll` nicht ausgeführt: `LLM_PROVIDER=fake` auf Anweisung, Ollama nicht gestartet.
  `make eval MODUS=voll` nur als Smoke-Test mit `fake` (Exit 0, `antwort_korrekt` 0.0 – erwartbar, `fake` antwortet nicht inhaltlich).
  Die echte Messung macht der Mensch.
- Fehler des Agenten und wie sie erkannt wurden:
  - Zeilen > 100 Zeichen in `app/eval.py` und `tests/test_eval.py`; von `make lint` gefunden, mit `ruff format` bzw. Umbruch behoben.
- Getroffene Annahmen:
  - Die Evaluation ruft die laufende API über HTTP (`EVAL_API_URL`, Standard `http://localhost:8000`), statt Code direkt
    zu importieren – gemessen wird, was Nutzer sehen. Läuft im Container mit `--user uid:gid`, braucht daher kein Schreibrecht außer in `/reports`.
  - Pro Frage eine Zeile im Bericht; im Modus `voll` ist eine `wissen`-Frage nur bestanden, wenn Retrieval **und** Antwort stimmen.
    Kennzahlen werden dagegen getrennt aus den Einzelprüfungen berechnet.
  - Kennzahlen ohne passende Fragen werden weggelassen; Schwellenwerte für fehlende Kennzahlen lösen keinen Fehler aus.
  - Moduswahl über `MODUS=voll` im Makefile → `EVAL_MODUS` im Container (zusätzlich `--modus`).
  - Makefile legt `reports/eval` vor dem Aufruf an, damit der Ordner der aufrufenden Person gehört (nicht root via Docker-Mount).
  - Der Chat-Rate-Limiter (60/min) reicht für die ~30 Fragen; es gibt keine Wartelogik bei 429.
  - CI-Job `eval` hatte die Prüfung „Spec 007 fertig" schon; ergänzt wurde nur der Artefakt-Upload (`if: always()`).
- Offene Punkte:
  - Schwellenwerte für `antwort_korrekt`/`grenzen_eingehalten` fehlen in `fragen.yaml` (geschützt); nach den ersten echten Messungen ergänzen.
  - Lokal fehlt `robot`; temporäre venv mit Robot + RequestsLibrary, keine Browser Library.
- Nachbesserung nach Review (Hinweise des Reviewers, auf Anweisung des Menschen umgesetzt):
  - Schwellenwert für eine Kennzahl ohne Messwerte → `bestanden: false`, Eintrag `fehler` im Bericht, Meldung auf stderr, Exit 1.
    „Muss berechnet werden" bestimmt `KENNZAHLEN_PRO_MODUS`; ein Schwellenwert für `antwort_korrekt` löst im Modus `retrieval` keinen Fehler aus.
  - HTTP-Fehler: 429/502/503/504 und Verbindungsfehler werden bis zu 5-mal mit Backoff (5/10/20/40 s) wiederholt, andere 4xx sofort als Fehler gemeldet.
    Die Ratenbegrenzung bleibt aktiv. Nach dem letzten Versuch bricht die Evaluation ab, schreibt den Bericht (betroffene Frage als nicht bestanden, `fehler` gesetzt) und endet mit Exit 1.
    Annahme: Bei Abbruch fehlen die restlichen Fragen im Bericht (nicht als „nicht bestanden" aufgeführt).
  - `Modus` ist `Literal["retrieval", "voll"]`; ungültiger Wert (Argument oder `EVAL_MODUS`) → argparse-Fehler, Exit 2.
  - Fehler des Agenten: erster Patch-Versuch scheiterte, weil `ruff format` eine Textstelle umgebrochen hatte; zweiter Test-Lauf rot durch Rekursion beim Patchen von `httpx.Client` (echte Klasse vorher gemerkt).
    11 neue pytest-Tests (327 gesamt).

## Spec 006 – Sicherheitsleitplanken und Datenschutz im Betrieb (2026-10-27)

- Durchläufe bis alle Tests grün: pytest 3 Läufe, `make acceptance SPEC=006` 1 Lauf (11/11, inkl. Suite 999).
  `make acceptance` (alle Specs, ohne `llm`): 52/53; fehlgeschlagen ist nur Spec 001 „Frontend zeigt die
  Überschrift", weil in meiner Test-Umgebung die Browser Library fehlt (siehe offene Punkte), kein Codefehler.
- `llm`-Tests (`make acceptance-llm`) nicht ausgeführt: `LLM_PROVIDER=fake` auf Anweisung, Ollama nicht gestartet.
- Fehler des Agenten und wie sie erkannt wurden:
  - Telefon-Regex schluckte Teile von UUIDs (`92125798-47ed-…`) und Slot-Daten; von
    `test_api_anfrage_ohne_personenbezogene_daten` gefunden. Jetzt: Bindestrich/Buchstaben direkt neben
    der Ziffernfolge schließen einen Treffer aus; Datumsmuster mit `(?<!\d)`/`(?!\d)` statt `\b`.
  - „sich das Leben genommen" wurde nicht erkannt (nur `nehmen`); Muster um `genomm` ergänzt.
  - `sed -i` (macOS) scheiterte; per Python ersetzt.
  - Nachtrag (auf Anweisung des Menschen): Notfall-Muster „schnappt nach Luft“ wurde im ersten Versuch mit umgekehrter Wortreihenfolge geschrieben; pytest wurde rot, der Agent hat es korrigiert.
- Getroffene Annahmen:
  - Zusatz des Menschen: `POST /api/termine/anfragen` ist ebenfalls begrenzt, mit eigenem Zähler pro IP
    und **20 Anfragen/Minute** (Zahl von mir gewählt, die Spec nennt keine). Auch 422-Aufrufe zählen.
  - Der Fehler-Log in `api_chat.py` ruft `redact()` explizit auf (zusätzlich zum Handler-Filter).
  - IP = `request.client.host`. Hinter einem Reverse Proxy wäre das die Proxy-Adresse; `X-Forwarded-For`
    wird bewusst nicht ausgewertet (fälschbar).
  - Seelische Krise hat Vorrang vor körperlichem Notfall; beide Antworten kommen aus `texte.py`.
  - Antwort mit Kanarienkennung (ohne Groß-/Kleinschreibung) → Standardantwort, `kategorie: "normal"`, keine Quellen.
  - Markierung als Daten (`<nutzereingabe>`, `<werkzeugergebnis>`) erfolgt in den Providern `ollama`/`anthropic`,
    nicht im `fake`-Provider, damit dessen Suche unverändert bleibt.
  - Das Datum im geloggten `slot_id` wird durch `redact()` zu `[DATUM]`; `test_termine.py` erwartet `redact(slot_id)`.
  - Bestehende Tests angepasst (`test_llm.py`, `test_chat.py`, `test_termine.py`), da Markierung und Limit-Fixtures neu sind.
- Offene Punkte:
  - Lokal fehlt `robot`; ich habe Robot + RequestsLibrary in einer temporären venv installiert. Browser Library
    nicht (Node-Init), daher Spec 001 Frontend-Test hier nicht lauffähig.
  - Ratenbegrenzer liegt im Prozessspeicher: bei mehreren Backend-Instanzen gilt das Limit je Instanz.
  - Notfall-Muster sind absichtlich weit gefasst; Falsch-Positive möglich (z. B. „nicht mehr bewegen" in anderem Kontext).

## Spec 005 – Terminanfrage über ein simuliertes Terminsystem (2026-10-27)

- Durchläufe bis alle Tests grün: 1 Abnahmelauf (spec-005 12/12 im ersten Lauf); pytest brauchte 2 Läufe.
- Fehler des Agenten und wie sie erkannt wurden:
  - `anfrage_stellen` las `zeile.anfrage_id` nach `commit()` außerhalb der Session
    (`DetachedInstanceError`, 500). Von pytest gefunden; die UUID wird jetzt vor dem Insert erzeugt.
  - `make acceptance` fand `robot` nicht im PATH; aufgerufen mit `ROBOT=.venv/bin/robot`
    (Robot liegt in `.venv/` im Repo-Wurzelverzeichnis).
- Getroffene Annahmen:
  - „Die nächsten 14 Tage ab heute" = heute bis heute + 13 Tage (14 Kalendertage inkl. heute).
  - `ab_datum` filtert nur innerhalb dieses Fensters; liegt es weiter als 13 Tage in der Zukunft,
    ist die Liste leer (kein Fehler).
  - Fachrichtung: Teilstring-Vergleich wie Spec 002 (`innere` → `Innere Medizin`); mehrere Treffer
    (z. B. `medizin` an std-005) oder keiner → 422. Leerer Wert → 422.
  - Slot-ID nur in kanonischer Form gültig (Fachrichtung exakt wie im Katalog, Offset `+01:00`/`+02:00`);
    andere Schreibweisen desselben Zeitpunkts (`Z`, kleingeschrieben) → 409.
  - „Belegt", wenn das erste Byte von `sha256(standort_id + fachrichtung + beginn_iso)` ≥ 128 ist.
  - `aktion` enthält die Termine des **letzten erfolgreichen** Aufrufs von `freie_termine_suchen`,
    auch wenn er leer war; fehlerhafte Aufrufe (unbekannter Standort, Fachrichtung) erzeugen keine `aktion`.
  - `GET /api/termine/anfragen/{id}` mit ungültiger UUID → 404 (statt FastAPI-422), wie im Vertrag
    nur `200`/`404` vorgesehen.
  - Die Tabelle speichert keine Status-Spalte, da es nur `angefragt` gibt (Bestätigung/Absage nicht im Umfang).
  - Engine mit `hide_parameters=True`: SQL-Fehler würden sonst Name/Telefon ins Log schreiben.
    Gilt für alle Abfragen, ändert aber nur Fehlermeldungen.
  - Unit-Tests für Speicher und API laufen gegen SQLite in-memory (das Projekt hat keine Test-DB);
    der Postgres-Pfad ist durch die Abnahmetests abgedeckt.
- `llm`-Tests (einmal am Ende, Ollama `qwen2.5:7b`, danach `ollama stop`): **44/47**.
  - 004 „Antwort hat die Struktur aus dem Vertrag": ReadTimeout (60 s) beim ersten Aufruf (Kaltstart des Modells).
  - 004 „Wissensfrage wird aus dem Dokument beantwortet": Antwort ohne „24 Stunden" (Antwortqualität).
  - 005 „Chat schlägt freie Termine vor": `aktion` war `null`, das Modell hat `freie_termine_suchen` also
    nicht erfolgreich aufgerufen. Ursache nicht belegt: Die Backend-Logs gingen beim Zurückschalten
    auf `fake` mit dem Container verloren. Vermutung: Das Modell hört nach `standorte_suchen` auf.
    Wegen des Arbeitsspeichers (16 GB) bewusst nicht wiederholt.
- Offene Punkte:
  - Für Spec 006 (Entscheidung des Menschen, 2026-10-27):
    - Rate-Limit für `POST /api/termine/anfragen` (heute kann ein Client alle freien Slots wegbuchen).
    - `api_chat.py` loggt bei `LlmError` die volle Fehlermeldung (`%s` mit `fehler`), obwohl laut
      Kommentar nur der Fehlertyp geloggt werden soll – über `redact()` bzw. nur den Typ loggen.
  - Werkzeugaufrufe nach Name im Chat-Log protokollieren (heute nur die Anzahl), damit sich
    `llm`-Fehlschläge wie oben ohne erneuten Lauf erklären lassen.
  - Ggf. Ein-Schritt-Variante: `freie_termine_suchen` mit Ort statt `standort_id`, damit kleine Modelle
    nicht zwei Werkzeuge verketten müssen (wäre eine Spec-Änderung).
  - Formular und Anzeige der Vorschläge folgen in Spec 008.
- Eingriffe durch den Menschen:
  - Spec-Änderung nach dem Review (gekennzeichnet als „Ergänzung (Mensch)" in Spec 005, Validierung):
    `telefon` muss mindestens 6 Ziffern enthalten. Umgesetzt als zusätzlicher Validator; neue
    pytest-Fälle (nur Leerzeichen, nur `+`/`-`/`/`, 5 Ziffern → 422; genau 6 Ziffern gültig). pytest 246/246.
  - Rate-Limit für Terminanfragen und Fehlerlog in `api_chat.py` auf Spec 006 verschoben (siehe Offene Punkte).
  - Vorgabe: Entwicklung mit `LLM_PROVIDER=fake`, `llm`-Tests höchstens einmal am Ende, danach
    `ollama stop qwen2.5:7b` (Rechner mit 16 GB ist beim letzten Mal eingefroren).
  - Während der Arbeit: Remote-Branch `spec/004-chat-assistent` löschen lassen – war auf GitHub schon
    gelöscht, nur die lokale Tracking-Referenz wurde per `git fetch --prune` entfernt.
- Review-Ergebnis: freigegeben nach 3 Runden. Runde 1 „Änderungen nötig“ (2 blockierend): abgelehnte `slot_id` wurde
  ungeprüft geloggt (Log-Injection, Namen im Log) und dieser Eintrag stand im Vorlagen-Codeblock.
  Beides behoben, pytest-Fall mit Zeilenumbruch und Namen in der `slot_id` ergänzt.
  Runde 2 „Änderungen nötig“ (1 blockierend): 422-Antworten wiederholten im Feld `input` Telefon,
  Geburtsdatum und Name im Klartext (in Runde 1 noch als Hinweis eingestuft). Behoben mit einem
  globalen Handler für `RequestValidationError`, der nur `loc`, `msg` und `type` liefert (gilt auch
  für `/api/chat`). Außerdem aus den Hinweisen: exakter Fachrichtungs-Treffer gewinnt,
  Löschjob wird beim Herunterfahren abgewartet. pytest 238/238.

## Spec 004 – Chat-Assistent mit Werkzeugen (2026-10-25)

- Durchläufe bis alle Tests grün: 1 für `make acceptance SPEC=004` (7/7 im ersten Lauf,
  `make acceptance` 30/30); `make lint` 2 Läufe, `make test` 151/151.
  Zusätzlich 7 Läufe der `llm`-Tests gegen Ollama (qwen2.5:7b): 8/11 → 9/11 → 10/11 →
  10/11 → 9/11 → 10/11 und 11/11 (siehe unten).
- Fehler des Agenten und wie sie erkannt wurden:
  - Zwei Zeilen über 100 Zeichen – von `make lint` (ruff E501) gefunden.
  - pytest-Tests übergaben `httpx.Client` an die SDKs; `openai` 3.x und `anthropic` 2.x
    nutzen `httpx2` und lehnen das ab – vom pytest-Lauf und mypy gefunden, Tests nutzen
    jetzt `httpx2.MockTransport` (kommt mit den SDKs, keine eigene Abhängigkeit).
  - Erster Systemprompt: qwen2.5:7b rief in den `llm`-Tests gar keine Werkzeuge auf und
    antwortete aus eigenem Wissen (Log: „0 Werkzeugaufrufe"). Ein Vergleich direkt gegen
    Ollama (je Variante 6–20 Anfragen) zeigte: Kein einzelner Abschnitt ist schuld,
    `tool_choice: "required"` ignoriert Ollama, eine Erinnerung als Folgenachricht hilft nicht.
    Eine Regel ganz oben im Prompt hebt die Quote auf ~70 %, nicht auf 100 %.
    Deshalb zusätzlich die Rückfallsuche im Code (siehe Annahmen).
  - Qwen lieferte Werkzeugaufrufe teils als Text, mit verstümmeltem öffnendem Tag
    („onaut", „isphere" statt `<tool_call>`); Ollama erkannte sie nicht. Mein erster Parser
    suchte nur das korrekte Tag – durch Zeitmessung des Sitzungs-Tests gefunden, jetzt zählt
    jedes JSON-Objekt `{"name": <Text>, "arguments": …}` in der Antwort.
  - `LLM_TIMEOUT_SECONDS=30` war zu knapp: Die Antwortrunde dauert auf diesem Rechner
    27–30 s (~1700 Prompt-Tokens, ~150 Antwort-Tokens) – vom Log (`APITimeoutError`) und einer
    Messung gefunden. Standard jetzt 60.
- Getroffene Annahmen:
  - Neue Abhängigkeiten: `openai` (Ollama über die OpenAI-kompatible Schnittstelle, später
    Azure über `base_url`) und `anthropic` – beide verlangt die Spec.
  - Neue Einstellung `LLM_TIMEOUT_SECONDS` (Standard 60, in `.env.example`). `OLLAMA_BASE_URL`
    wird in `docker-compose.yml` mit Standard `http://host.docker.internal:11434/v1` durchgereicht.
    SDK-Wiederholungen: Ollama 0, Anthropic 1.
  - **Quellen** („gegeben **und** gestützt"): Das Modell nennt in einer letzten Zeile
    `Quellen: <dokument>, …`; der Server entfernt die Zeile und übernimmt nur Dokumente, die
    das Modell tatsächlich bekommen hat und die als ganzer Eintrag (Dateiname oder Titel)
    genannt sind. Fehlt die Zeile oder passt kein Eintrag → `quellen: []` (nach Review, siehe
    unten). Der Fake-Provider schreibt seine Quellenzeile (Dokumente aller Treffer) selbst.
    `standorte.json` gilt als geliefert, wenn `standorte_suchen` mindestens einen Standort fand.
  - **Rückfallsuche:** Antwortet das Modell in der ersten Runde ohne Werkzeug, verwirft der
    Server die Antwort, ruft `wissen_suchen(frage=<Nachricht>)` auf und lässt das Modell
    erneut antworten. Begründung: „antwortet nur auf Grundlage dieser Ergebnisse" wiegt
    schwerer als „entscheidet selbst"; wenn das Modell Werkzeuge nutzt, entscheidet es weiter selbst.
    Nebenwirkung: Auch Grüße („Hallo") lösen eine Suche aus (eine LLM-Runde mehr).
  - Werkzeuglimit: 4 Aufrufe pro Nachricht. Weitere Aufrufe derselben Antwort bekommen ein
    Fehlerergebnis (jeder Aufruf braucht eines), danach eine Runde mit `tool_choice: none`;
    liefert das Modell trotzdem Aufrufe, zählt nur sein Text.
  - Sitzungen speichern nur Nutzernachrichten und Antworttexte, keine Werkzeugaufrufe/-ergebnisse;
    gekürzt wird paarweise, damit der Verlauf mit einer Nutzernachricht beginnt. Fehlerantworten
    (`kategorie: "fehler"`) kommen nicht in den Verlauf. Eine unbekannte `sitzung_id` startet
    eine neue Sitzung unter dieser ID; eine `sitzung_id`, die keine UUID ist, ergibt `422`.
  - `nachricht` wird vor der Längenprüfung getrimmt (nur Leerzeichen → `422`), wie in Spec 003.
  - Die Fehlermeldung verweist allgemein auf „Ihren Standort", weil es keine zentrale Nummer gibt.
  - Logs: nur Länge der Nachricht, Zahl der Werkzeugaufrufe und Quellen bzw. der Fehlertyp;
    ein pytest-Test prüft, dass der Nachrichtentext nicht im Log steht. Werkzeugfehler an das
    Modell enthalten nur Feldnamen und Fehlertypen, keine Eingabewerte.
  - Prompt-Injection-Kennzeichnung und Kanarien-Prüfung der Antwort gehören zu Spec 006;
    der Systemprompt enthält die Kennung bereits mit dem Verbot, sie auszugeben.
- Offene Punkte:
  - Die `llm`-Tests sind mit qwen2.5:7b nicht stabil grün. Sporadisch: „Unbekanntes wird nicht
    erfunden" (Modell sagt richtig „keine Standorte", verweist aber nicht aufs Telefon) und
    „Wissensfrage …" (nennt die 24 Stunden nicht). Ein größeres Modell oder Anthropic dürfte
    das beheben; nicht geprüft (kein API-Key verwendet).
  - Auf langsamer Hardware kann eine Anfrage mit mehreren Runden das 60-s-Zeitlimit der
    Robot-Session überschreiten. Ein Gesamtbudget pro Anfrage wäre eine Option.
  - Der Sitzungsspeicher ist pro Prozess; mit mehreren Uvicorn-Workern fänden Folgeanfragen
    ihren Verlauf nicht immer (laut Spec nur im Speicher, daher so gelassen).
  - Ein Datenbankfehler während eines Werkzeugaufrufs ergibt `500` (kein Anbieterfehler im
    Sinne von Anforderung 6).
- Eingriffe durch den Menschen:
  - Entscheidung nach dem PR: Die Rückfallsuche (Server sucht selbst, wenn das Modell kein
    Werkzeug nutzt) bleibt als **bewusste Abweichung** von „Das LLM entscheidet selbst".
    Begründung: Antworten sollen sich immer auf Werkzeugergebnisse stützen; das ist wichtiger
    als die freie Werkzeugwahl. In den Umsetzungsnotizen von Spec 004 vermerkt.
  - Nach Review Runde 2: Status zurück auf `in Arbeit`, sonst keine Änderung. Das weitere
    Vorgehen bei den `llm`-Tests (Modell, Abnahme, Nachfordern der Quellenzeile) ist offen.
- Review-Ergebnis Runde 1: Änderungen nötig, 1 blockierender Punkt:
  - Fehlte die Quellenzeile, wurden alle gelieferten Dokumente zu Quellen – auch bei
    „Dazu habe ich keine Informationen gefunden" (verstößt gegen „gestützt"). Mein Fehler:
    Ich hatte den Rückfall als Annahme festgelegt, statt die Spec-Regel strikt umzusetzen.
    Behoben: ohne passende Zeile `[]`; Abgleich pro Eintrag statt über Teilstrings.
    Messung vorher gegen Ollama: qwen2.5:7b schreibt die Zeile in 5 von 6 Antworten.
  - Hinweise ebenfalls umgesetzt: Text-Werkzeugaufrufe nur mit Namen eines angebotenen
    Werkzeugs und nur in Runden mit erlaubten Werkzeugen; `try` in `werkzeuge.py` nur um
    Parsen/Validieren (Ausführungsfehler fliegen weiter); höchstens 10 000 Sitzungen
    (älteste unbenutzte fällt weg); Startwarnung nennt die URL nur bei `ollama`;
    Literal `LlmProvider` → `LlmProviderName` (Verwechslung mit dem Protocol).
  - Nicht umgesetzt: Rückfallsuche wählt immer `wissen_suchen`, auch bei Standortfragen
    (vom Menschen so entschieden; eine Auswahl wäre wieder eine Heuristik).
    21 Nachrichten ans Modell (20 im Verlauf + neue) – so gelassen.
  - `make lint` grün, `make test` 158/158 (lokal und im Container), `make acceptance SPEC=004`
    7/7, `make acceptance` 30/30.
  - Kontrolllauf `llm`-Tests danach: 9/11. „Wissensfrage …" scheiterte, weil das Modell die
    Quellenzeile wegließ (`quellen: []`) – Preis der strikten Regel; vorher hätte der Rückfall
    die Quelle geliefert. „Unbekanntes …" wie bisher (kein Verweis aufs Telefon).
- Review-Ergebnis Runde 2: Änderungen nötig, 1 blockierender Punkt: Status `fertig` war
  falsch, weil die `llm`-Tests mit Tag `spec-004` nicht grün sind (9/11). Mein Fehler: Ich
  hatte „fertig" nur an `make acceptance` (ohne `llm`) festgemacht, CLAUDE.md verlangt
  aber alle Tests mit dem Tag. Status zurückgesetzt. Hinweise (nur letzte Zeile als Quellenzeile,
  Titel mit Komma, Text-Werkzeugaufrufe ab Spec 005 neu bewerten, `max_retries=1` bei
  Anthropic, Nutzernachricht ungefiltert ans LLM bis Spec 006, 500 bei DB-Fehler) offen.
- Nachtrag 2026-10-27: CLAUDE.md geändert (PR #5, Mensch) – `llm`-Tests sind Qualitätsmessung,
  kein Merge-Kriterium. `main` in den Branch gemergt, Status wieder `fertig`.
  **Letztes `llm`-Ergebnis: 9/11** (Ollama qwen2.5:7b, Kontrolllauf nach Review Runde 1;
  rot: „Wissensfrage …" – Quellenzeile fehlte – und „Unbekanntes wird nicht erfunden" –
  kein Verweis aufs Telefon). Kein neuer `llm`-Lauf. Hinweise aus Runde 2 bleiben offen.
  Danach `make lint` grün, `make test` 158/158, `make acceptance SPEC=004` 7/7,
  `make acceptance` 30/30. Zwei Läufe direkt nach `make up` scheiterten an der Verbindung
  (Backend noch im Start: 0/7, dann 29/30 mit `Connection reset` beim Health-Test);
  nach Bereitschaft von `/api/health` grün. Offener Punkt: `make acceptance` wartet nicht
  auf ein bereites Backend.

## Spec 003 – Wissensbasis und semantische Suche (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 9/9 im ersten Lauf, `make acceptance` 23/23);
  `make lint` brauchte 3 Läufe, `make test` 79/79 (nach Review-Fixes).
- Fehler des Agenten und wie sie erkannt wurden:
  - Import-Reihenfolge in `app/main.py` (ruff I001) und eine von `ruff format` anders
    umbrochene Testsignatur – von `make lint` gefunden.
  - Falscher `type: ignore`-Code in einem pytest-Test (mypy strict meldete `no-untyped-call`);
    jetzt mit `ClauseElement` typisiert.
  - Eine `frage` nur aus Leerzeichen lieferte 200 mit beliebigen Treffern statt 422 – derselbe
    Fehlertyp wie in Spec 002, vom Reviewer gefunden. Behoben mit
    `StringConstraints(strip_whitespace=True, …)`, pytest-Fälle `"   "` und `"\n\t"` ergänzt.
- Getroffene Annahmen:
  - Neue Abhängigkeiten: `fastembed` (Spec verlangt es), `pgvector` (SQLAlchemy-Typ `Vector`
    und `cosine_distance`), `pyyaml` (YAML-Kopf), dev: `types-PyYAML`.
  - `inhalt_hash` = SHA-256 über Modellname + Einbettungstext (`"<titel> – <abschnitt>\n\n<text>"`).
    Ein Modellwechsel bettet so alles neu ein. Abgleich über `(dokument, inhalt_hash)`:
    Ein geänderter Abschnitt zählt als 1 neu + 1 gelöscht. `position` und `fachrichtungen`
    (nicht eingebettet) werden bei unveränderten Abschnitten aktualisiert.
  - „gelöscht" zählt alle entfernten Abschnitte (gelöschte Dateien und geänderte Abschnitte).
    Manuell geprüft mit einer Kopie von `data/wissen` ohne `termin-absagen.md`:
    `0 neu, 29 unverändert, 4 gelöscht`; danach mit Originaldaten `4 neu, 29 unverändert, 0 gelöscht`.
  - Spalte `embedding vector(384)` fest (Dimension des Standardmodells). Liefert ein anderes
    `EMBEDDING_MODEL` eine andere Dimension, bricht der Ingest mit klarer Meldung ab;
    dann braucht es eine neue Migration.
  - Zusätzliche Spalte `position` (Reihenfolge im Dokument); die Spec nennt „mindestens" die Felder.
  - Leere Abschnitte werden mitgezählt (ein Abschnitt pro `##`, wie in der Spec); `###` trennt nicht.
  - „Höchstens 2 pro Dokument" per `row_number() OVER (PARTITION BY dokument …)` über alle
    Abschnitte. Das nutzt den HNSW-Index nicht, ist aber exakt; bei 33 Abschnitten ~1 ms.
    Der Index existiert wie gefordert für spätere größere Datenmengen.
  - Das Modell wird im Dockerfile geladen (`FASTEMBED_CACHE_PATH=/opt/fastembed`), danach
    `HF_HUB_OFFLINE=1`. Der Backend-Start lädt das Modell aus dem Cache in den Speicher
    (Lifespan), nicht beim ersten Request. `docker-compose.yml` reicht `EMBEDDING_MODEL` als
    Build-Argument durch.
  - Logging: Spec 006 (`redact()`) gibt es noch nicht. Die Suche loggt nur Trefferzahl und Dauer;
    ein pytest-Test prüft, dass der Fragetext nicht im Log steht. Damit App-Logs überhaupt
    erscheinen, setzt `app/main.py` `logging.basicConfig(level=INFO)` (Uvicorn konfiguriert nur
    seine eigenen Logger). Spec 006 ersetzt das durch den Redaktionsfilter.
  - `GET /api/wissen/dokumente` gruppiert nach `dokument` (Titel per `min()`, nach Ingest ohnehin eindeutig).
  - README-Statustabelle: 002 und 003 auf `fertig` gesetzt (002 war nach dem Merge noch `offen`).
- Offene Punkte:
  - Das Modell schneidet Eingaben nach 128 Token ab. 1 von 33 Abschnitten ist länger
    („Ernährung in den Tagen davor", 159 Token): Der Absatz zu klaren Flüssigkeiten am Vortag
    fließt nicht ins Embedding ein (der Text im Treffer ist vollständig). Kandidat für die
    Eval in Spec 007 (z. B. Chunking nach Absätzen oder anderes Modell).
  - Scores im Abstand: „Koloskopie essen" → darmspiegelung 0,734 vs. magenspiegelung 0,605;
    „Termin absagen" → termin-absagen 0,793 vs. 0,561. Die Tests sind also nicht knapp.
  - Das Docker-Image wächst durch fastembed/onnxruntime und das Modell (~220 MB).
  - Für Spec 006: Die Standard-422-Antwort von FastAPI enthält im Feld `input` den Eingabewert,
    bei zu langer `frage` also den kompletten Fragetext (geht nur an den Client zurück, nicht ins Log).
    Klären, ob Validierungsfehler Eingaben zurückgeben dürfen; sonst eigener
    `RequestValidationError`-Handler ohne `input`.
- Eingriffe durch den Menschen:
  - Nach dem Review: Hinweise 1 und 2 in diesen PR aufnehmen, Hinweis 3 als offenen Punkt für Spec 006.
    - `make ingest` bricht ab (Exit-Code 1, Meldung „Ingest abgebrochen, nichts gelöscht: …"),
      wenn `/data/wissen` fehlt oder keine `*.md` enthält. Die Dokumente werden vor jedem
      Datenbank- oder Modellzugriff gelesen; pytest prüft, dass weder Migrationen, Engine noch
      Modell angefasst werden. Im Container geprüft: beide Fälle Exit 1, danach weiterhin
      `0 neu, 33 unverändert, 0 gelöscht`.
    - Wissensdokumente werden mit `utf-8-sig` gelesen; pytest-Fall mit BOM.
- Review-Ergebnis: freigegeben nach 2 Runden. Runde 1: ein blockierender Punkt (Frage nur aus
  Leerzeichen → 200 statt 422), behoben. Runde 2: keine blockierenden Punkte. Hinweise
  im PR-Kommentar; zwei davon auf Wunsch des Menschen umgesetzt (siehe Eingriffe).

## Spec 002 – Standortsuche (2026-10-25)

- Durchläufe bis alle Tests grün: 1 (Abnahme 11/11 im ersten Lauf, `make acceptance` 14/14);
  `make lint` brauchte 2 Läufe.
- Fehler des Agenten und wie sie erkannt wurden:
  - Docstring in `app/standorte.py` war länger als 100 Zeichen – von `make lint` (ruff E501) gefunden.
  - Ein Filter nur aus Leerzeichen (`?fachrichtung=%20`) galt nicht als leer und fand alle
    Standorte mit Leerzeichen in der Fachrichtung („Innere Medizin") – entgegen der eigenen
    Annahme unten. Vom Reviewer gefunden, behoben (`strip()`, danach leer = kein Filter).
  - Zerlegte Umlaute (NFD, z. B. von macOS) wurden nicht umschrieben, `gynäk` in NFD fand
    nichts – vom Reviewer gefunden, behoben (`unicodedata.normalize("NFC", …)` vor dem Vergleich).
  - Nach dem Fix formatierte `ruff format` eine Testzeile anders – von `make lint` gefunden.
- Getroffene Annahmen:
  - Die Umlaut-Umschreibung (`ä→ae`, `ö→oe`, `ü→ue`, `ß→ss`, plus `casefold()`) gilt für
    `fachrichtung` **und** `ort` (`nuernberg` findet `Nürnberg`). Die Spec verlangt sie nur
    für `fachrichtung`; eine gemeinsame Vergleichsfunktion ist einfacher und widerspricht Anf. 3 nicht.
  - Leerer Filterwert (`?fachrichtung=`) oder nur Leerzeichen wirkt wie kein Filter;
    Leerzeichen am Rand werden entfernt.
  - `fachrichtung` und `ort` sind auf 100 Zeichen begrenzt (`Query(max_length=100)`); längere
    Werte liefern `422` (FastAPI-Standard). Die Spec nennt keine Grenze; Vorschlag des Reviewers
    als Eingabeprüfung vor Spec 004.
  - `/api/fachrichtungen` sortiert nach der normalisierten Form, damit ein Wort mit Umlaut am
    Anfang (z. B. `Ärztlicher …`) bei `A` einsortiert wird und nicht hinter `Z`.
  - Das Modell `Standort` lehnt unbekannte Felder ab (`extra="forbid"`): Weicht
    `standorte.json` vom Vertrag ab, startet das Backend nicht, statt Felder still zu verwerfen.
  - `DATA_DIR` in `.env.example` ergänzt (Standard `/data`).
- Offene Punkte:
  - Der Katalog wird nur beim Start geladen; Änderungen an `standorte.json` brauchen einen Neustart
    (laut Spec so gewollt).
- Eingriffe durch den Menschen:
  - Nach dem Review: alle drei Hinweise (Leerzeichen, NFC, Längengrenze) mit pytest-Fällen
    in diesen PR aufnehmen.
- Review-Ergebnis: freigegeben nach 1 Runde (keine blockierenden Punkte, Hinweise im PR-Kommentar).
  Drei Hinweise danach umgesetzt; `make lint` grün, `make test` 43/43 (lokal und im Container),
  `make acceptance` 14/14 (spec-002 11/11).

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
