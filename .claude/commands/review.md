---
description: Lässt den aktuellen Branch von einem unabhängigen Reviewer-Agenten prüfen
---

Starte den Subagenten **reviewer** und lass ihn den Unterschied zwischen dem
aktuellen Branch und `main` prüfen (`git diff main...HEAD`).

Gib ihm nur diese Informationen mit: die Nummer der Spec aus dem Branch-Namen
und den Hinweis, `CLAUDE.md` und die Spec selbst zu lesen. Gib ihm **nicht**
deine eigene Einschätzung der Änderungen, damit er unvoreingenommen prüft.

Fasse sein Ergebnis zusammen. Wenn er Punkte mit Schwere „blockierend" findet,
behebe sie, führe die Tests erneut aus und starte den Review noch einmal.
Poste das finale Review-Ergebnis mit `gh pr comment` in den Pull Request.
