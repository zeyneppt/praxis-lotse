# Spec 006 – Sicherheitsleitplanken und Datenschutz im Betrieb

**Status:** fertig
**Abhängigkeiten:** 004
**Abnahmetests:** `tests/acceptance/006_leitplanken.robot` (Tag `spec-006`)

## Ziel

Der Assistent erkennt Notfälle zuverlässig, gibt keine medizinische Beratung,
lässt sich nicht durch Prompt-Injection umprogrammieren und schreibt keine
personenbezogenen Daten in Logs.

## Anforderungen

1. **Notfallerkennung, regelbasiert, vor dem LLM.** Modul
   `backend/app/leitplanken/notfall.py`. Erkennt mindestens diese Muster
   (ohne Groß-/Kleinschreibung, auch mit Umlaut-Umschreibung):
   - körperlich: Brustschmerz, Atemnot, keine/schlecht Luft, bewusstlos,
     ohnmächtig, Schlaganfall, Lähmung, „nicht mehr bewegen", undeutlich
     sprechen / Sprachstörung, starke Blutung / „blutet stark", Krampfanfall
   - seelisch: Suizid, „das Leben nehmen", „umbringen" (auf sich bezogen),
     „nicht mehr leben"
   Bei einem Treffer wird **das LLM nicht aufgerufen**. Antwort mit
   `kategorie: "notfall"`, `quellen` = Notfalldokument, `aktion: null`:
   - körperlich: Aufforderung, sofort die **112** anzurufen
   - seelisch: TelefonSeelsorge **0800 111 0 111** und **0800 111 0 222**,
     bei akuter Gefahr **112**; einfühlsamer Ton
   Die Texte stehen in `backend/app/leitplanken/texte.py`, nicht im LLM-Prompt.
   In der körperlichen Notfallantwort ist die 112 die erste genannte Nummer.
   Die Erkennung soll lieber einmal zu oft als einmal zu wenig auslösen.
2. **Keine medizinische Beratung** (Systemprompt): keine Diagnosen, keine
   Einschätzung von Symptomen, keine Empfehlung, Medikamente zu nehmen,
   abzusetzen oder zu dosieren. Stattdessen Verweis auf die Ärztin oder den
   Arzt, bei Dringlichkeit auf 116117. Organisatorische Hinweise aus den
   Dokumenten (z. B. „Medikamente im Vorgespräch besprechen") sind erlaubt.
3. **Prompt-Injection:** Nutzereingaben und Werkzeugergebnisse werden im Prompt
   klar als Daten gekennzeichnet. Der Systemprompt untersagt, Anweisungen aus
   diesen Daten zu befolgen oder den Systemprompt preiszugeben. Zusätzlich
   prüft der Server jede LLM-Antwort: Enthält sie `PL-KANARIE-7731`, wird sie
   durch eine Standardantwort ersetzt und ein Warn-Log ohne Inhalt geschrieben.
4. **Redaktion in Logs:** Funktion `app.logging.redact(text: str) -> str`
   ersetzt Telefonnummern durch `[TELEFON]`, E-Mail-Adressen durch `[EMAIL]`
   und Datumsangaben (`TT.MM.JJJJ`, `JJJJ-MM-TT`) durch `[DATUM]`.
   Alle Log-Ausgaben der App laufen über einen Filter, der `redact()` anwendet.
   Chat-Nachrichten werden höchstens als Länge geloggt, nie im Wortlaut.
   pytest-Tests decken mindestens 10 Beispiele ab.
5. **Transparenz (EU AI Act Art. 50):** `ki_hinweis` in jeder Chat-Antwort
   (bereits Spec 004) und sichtbar in der Oberfläche (Spec 008).
6. **Begrenzung:** höchstens 60 Chat-Nachrichten pro Minute und IP-Adresse (gleitendes Fenster),
   darüber `429` `{"detail": "Zu viele Anfragen. Bitte warten Sie einen Moment."}`.

   Der zugehörige Test liegt in `999_ratenbegrenzung.robot` und läuft als letzte Suite.

## API-Vertrag

Keine neuen Endpunkte. Änderungen an `POST /api/chat`: `kategorie: "notfall"`
wie oben; `429` bei Überschreitung des Limits.

## Nicht im Umfang

- KI-basierte Klassifikation von Notfällen (regelbasiert ist hier bewusst
  gewählt: nachvollziehbar, testbar, ohne LLM-Ausfallrisiko)

## Umsetzungsnotizen

Plan:

1. `app/leitplanken/texte.py`: Notfalltexte (körperlich, seelisch), Standardantwort, Kanarienkennung, Notfalldokument.
2. `app/leitplanken/notfall.py`: `erkenne_notfall(text)` mit normalisierten Regex-Mustern (Umlaute umschrieben, Groß-/Kleinschreibung egal); seelisch hat Vorrang.
3. `run_chat` prüft den Notfall **vor** dem ersten LLM-Aufruf und liefert `kategorie: "notfall"` mit Notfalldokument als Quelle; `aktion` bleibt `null`.
4. `run_chat` ersetzt Antworten mit `PL-KANARIE-7731` durch die Standardantwort (Warn-Log ohne Inhalt).
5. `app/leitplanken/daten.py`: Nutzereingaben und Werkzeugergebnisse werden in den Providern als `<nutzereingabe>`/`<werkzeugergebnis>` markiert; Systemprompt um Abschnitt „Eingaben sind Daten" erweitert.
6. `app/logging.py`: `redact()`, `RedactFilter` an allen Handlern (Root und Uvicorn), `configure_logging()` ersetzt `basicConfig` in `main.py`.
7. `app/ratenbegrenzung.py`: gleitendes Fenster pro IP (60/Minute), als Dependency am Chat-Endpunkt, Antwort `429`.
8. pytest-Tests für Notfall, Redaktion (≥ 10 Beispiele), Kanarie, Datenmarkierung, Ratenbegrenzung.

Zusatz (Mensch): `POST /api/termine/anfragen` ist ebenfalls je IP begrenzt (20/Minute, eigener Zähler);
der Fehler-Log in `api_chat.py` läuft explizit über `redact()`.
