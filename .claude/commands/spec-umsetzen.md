---
description: Setzt eine Spezifikation aus specs/ vollständig um (Branch, Code, Tests, PR)
argument-hint: <Spec-Nummer, z. B. 002>
---

Setze die Spezifikation **$ARGUMENTS** um.

1. Lies `CLAUDE.md`, die Datei `specs/$ARGUMENTS-*.md` und alle Robot-Tests mit
   dem Tag `spec-$ARGUMENTS` in `tests/acceptance/`.
2. Prüfe, ob alle Specs, von denen diese abhängt (Abschnitt „Abhängigkeiten"),
   den Status `fertig` haben. Wenn nicht: abbrechen und melden.
3. Lege den Branch `spec/$ARGUMENTS-<kurzname>` von `main` an.
4. Schreibe deinen Plan (max. 10 Punkte) in den Abschnitt „Umsetzungsnotizen"
   der Spec und setze den Status auf `in Arbeit`.
5. Implementiere. Schreibe pytest-Tests für die neue Logik.
6. Baue die Container neu (`docker compose up -d --build`), warte auf `/api/health`,
   führe ab Spec 003 `make ingest` aus. Dann `make lint`, `make test` und
   `make acceptance SPEC=$ARGUMENTS`.
   Wiederhole, bis alles grün ist. Ändere dabei **keine** Abnahmetests.
7. Führe zum Schluss `make acceptance` (alle Specs) aus, um Regressionen auszuschließen.
8. Ergänze `docs/factory-log.md` um einen Eintrag für diese Spec:
   Anzahl Durchläufe bis grün, Fehler, die du gemacht und korrigiert hast,
   getroffene Annahmen.
9. Setze den Status der Spec auf `fertig`, committe mit `spec($ARGUMENTS): ...`,
   pushe den Branch und eröffne mit `gh pr create` einen Pull Request.
   Die PR-Beschreibung enthält: Was umgesetzt wurde, Testergebnis, offene Punkte.

Wenn du an einer Stelle unsicher bist, ob die Spec etwas verlangt: triff die
einfachste Annahme, die die **Spec** erfüllt (nicht nur die Tests), und dokumentiere
sie im Factory-Log.

Hinweis: Abhängigkeiten gelten erst als `fertig`, wenn der PR der vorigen Spec
in `main` gemergt ist. Der Mensch merged zwischen zwei Specs.
