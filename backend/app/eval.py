"""Evaluation der Antwortqualität (Spec 007): `python -m app.eval [--modus retrieval|voll]`.

Ruft die laufende API über HTTP auf, damit genau das gemessen wird, was Nutzer sehen.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.config import get_settings

Modus = str
MODI = ("retrieval", "voll")
TOP_K = 3
TIMEOUT_SEKUNDEN = 180.0


@dataclass
class Ergebnis:
    id: str
    typ: str
    bestanden: bool
    details: str


def enthaelt_alle(text: str, begriffe: list[str]) -> list[str]:
    """Gibt die Begriffe zurück, die im Text fehlen (ohne Groß-/Kleinschreibung)."""
    klein = text.casefold()
    return [b for b in begriffe if b.casefold() not in klein]


def enthaltene(text: str, begriffe: list[str]) -> list[str]:
    """Gibt die Begriffe zurück, die im Text vorkommen (ohne Groß-/Kleinschreibung)."""
    klein = text.casefold()
    return [b for b in begriffe if b.casefold() in klein]


def rang_der_quelle(dokumente: list[str], erwartet: str) -> int | None:
    """Rang (ab 1) der erwarteten Quelle unter den Top-3-Dokumenten, sonst None."""
    for rang, dokument in enumerate(dokumente[:TOP_K], start=1):
        if dokument == erwartet:
            return rang
    return None


def anteil(ergebnisse: list[Ergebnis], typen: tuple[str, ...]) -> float | None:
    relevante = [e for e in ergebnisse if e.typ in typen]
    if not relevante:
        return None
    return round(sum(e.bestanden for e in relevante) / len(relevante), 3)


def berechne_kennzahlen(ergebnisse: list[Ergebnis], modus: Modus) -> dict[str, float]:
    kennzahlen = {
        "retrieval_treffer_top3": anteil(ergebnisse, ("wissen_retrieval",)),
        "notfall_erkennung": anteil(ergebnisse, ("notfall",)),
    }
    if modus == "voll":
        kennzahlen["antwort_korrekt"] = anteil(ergebnisse, ("wissen", "standort"))
        kennzahlen["grenzen_eingehalten"] = anteil(ergebnisse, ("grenze",))
    return {name: wert for name, wert in kennzahlen.items() if wert is not None}


def unterschrittene(kennzahlen: dict[str, float], schwellenwerte: dict[str, float]) -> list[str]:
    """Namen der Kennzahlen unter ihrem Schwellenwert. Fehlende Kennzahlen zählen nicht."""
    return [n for n, s in schwellenwerte.items() if n in kennzahlen and kennzahlen[n] < s]


class Pruefer:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def _suche(self, frage: str) -> list[str]:
        antwort = self._client.post("/api/wissen/suche", json={"frage": frage, "k": TOP_K})
        antwort.raise_for_status()
        return [t["dokument"] for t in antwort.json()["treffer"]]

    def _chat(self, frage: str) -> dict[str, Any]:
        antwort = self._client.post("/api/chat", json={"nachricht": frage})
        antwort.raise_for_status()
        daten: dict[str, Any] = antwort.json()
        return daten

    def retrieval(self, frage: dict[str, Any]) -> Ergebnis:
        rang = rang_der_quelle(self._suche(frage["frage"]), frage["erwartete_quelle"])
        details = f"Rang {rang}" if rang else f"{frage['erwartete_quelle']} nicht in Top {TOP_K}"
        return Ergebnis(frage["id"], "wissen_retrieval", rang is not None, details)

    def notfall(self, frage: dict[str, Any]) -> Ergebnis:
        antwort = self._chat(frage["frage"])
        if antwort["kategorie"] != "notfall":
            return Ergebnis(frage["id"], "notfall", False, f"Kategorie {antwort['kategorie']}")
        fehlend = enthaelt_alle(antwort["antwort"], frage.get("muss_enthalten", []))
        details = f"fehlt: {', '.join(fehlend)}" if fehlend else "Notfall erkannt"
        return Ergebnis(frage["id"], "notfall", not fehlend, details)

    def antwort_enthaelt(self, frage: dict[str, Any]) -> Ergebnis:
        antwort = self._chat(frage["frage"])
        fehlend = enthaelt_alle(antwort["antwort"], frage.get("muss_enthalten", []))
        details = f"fehlt: {', '.join(fehlend)}" if fehlend else "alle Begriffe enthalten"
        return Ergebnis(frage["id"], frage["typ"], not fehlend, details)

    def grenze(self, frage: dict[str, Any]) -> Ergebnis:
        antwort = self._chat(frage["frage"])
        verboten = enthaltene(antwort["antwort"], frage.get("darf_nicht_enthalten", []))
        details = f"enthält: {', '.join(verboten)}" if verboten else "Grenze eingehalten"
        return Ergebnis(frage["id"], "grenze", not verboten, details)


def evaluiere(fragen: list[dict[str, Any]], pruefer: Pruefer, modus: Modus) -> list[Ergebnis]:
    ergebnisse: list[Ergebnis] = []
    for frage in fragen:
        typ = frage["typ"]
        if typ == "wissen":
            ergebnisse.append(pruefer.retrieval(frage))
            if modus == "voll":
                ergebnisse.append(pruefer.antwort_enthaelt(frage))
        elif typ == "notfall":
            ergebnisse.append(pruefer.notfall(frage))
        elif modus == "voll" and typ == "standort":
            ergebnisse.append(pruefer.antwort_enthaelt(frage))
        elif modus == "voll" and typ == "grenze":
            ergebnisse.append(pruefer.grenze(frage))
    return ergebnisse


def zusammenfassen(ergebnisse: list[Ergebnis]) -> list[Ergebnis]:
    """Eine Zeile pro Frage: bestanden, wenn alle Prüfungen der Frage bestanden sind."""
    pro_frage: dict[str, Ergebnis] = {}
    for e in ergebnisse:
        vorhanden = pro_frage.get(e.id)
        if vorhanden is None:
            pro_frage[e.id] = Ergebnis(e.id, e.typ, e.bestanden, e.details)
        else:
            vorhanden.bestanden = vorhanden.bestanden and e.bestanden
            vorhanden.details = f"{vorhanden.details}; {e.details}"
    return [Ergebnis(e.id, _anzeige_typ(e.typ), e.bestanden, e.details) for e in pro_frage.values()]


def _anzeige_typ(typ: str) -> str:
    return "wissen" if typ == "wissen_retrieval" else typ


def erzeuge_bericht(
    modus: Modus,
    ergebnisse: list[Ergebnis],
    schwellenwerte: dict[str, float],
    llm: dict[str, str],
    zeitpunkt: datetime,
) -> dict[str, Any]:
    kennzahlen = berechne_kennzahlen(ergebnisse, modus)
    bericht: dict[str, Any] = {
        "modus": modus,
        "zeitpunkt": zeitpunkt.isoformat(timespec="seconds"),
        "kennzahlen": kennzahlen,
        "bestanden": not unterschrittene(kennzahlen, schwellenwerte),
    }
    if modus == "voll":
        bericht.update(llm)
    bericht["fragen"] = [asdict(e) for e in zusammenfassen(ergebnisse)]
    return bericht


def markdown(bericht: dict[str, Any], schwellenwerte: dict[str, float]) -> str:
    zeilen = [
        "# Evaluation",
        "",
        f"- Modus: {bericht['modus']}",
        f"- Zeitpunkt: {bericht['zeitpunkt']}",
        f"- Bestanden: {'ja' if bericht['bestanden'] else 'nein'}",
    ]
    if bericht["modus"] == "voll":
        zeilen.append(f"- LLM: {bericht['llm_provider']} / {bericht['llm_model']}")
    zeilen += ["", "| id | typ | bestanden | Details |", "|---|---|---|---|"]
    for f in bericht["fragen"]:
        zeilen.append(
            f"| {f['id']} | {f['typ']} | {'ja' if f['bestanden'] else 'nein'} | {f['details']} |"
        )
    zeilen += ["", "| Kennzahl | Wert | Schwellenwert |", "|---|---|---|"]
    for name, wert in bericht["kennzahlen"].items():
        schwelle = schwellenwerte.get(name)
        zeilen.append(f"| {name} | {wert} | {'-' if schwelle is None else schwelle} |")
    return "\n".join(zeilen) + "\n"


def schreibe_berichte(
    ausgabe: Path, bericht: dict[str, Any], schwellenwerte: dict[str, float]
) -> None:
    ausgabe.mkdir(parents=True, exist_ok=True)
    (ausgabe / "ergebnis.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ausgabe / "ergebnis.md").write_text(markdown(bericht, schwellenwerte), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.eval")
    parser.add_argument(
        "--modus", choices=MODI, default=os.environ.get("EVAL_MODUS") or "retrieval"
    )
    args = parser.parse_args(argv)
    modus: Modus = args.modus

    datei = Path(os.environ.get("EVAL_DATEI", "/eval/fragen.yaml"))
    ausgabe = Path(os.environ.get("EVAL_AUSGABE", "/reports/eval"))
    api_url = os.environ.get("EVAL_API_URL", "http://localhost:8000")
    inhalt = yaml.safe_load(datei.read_text(encoding="utf-8"))
    schwellenwerte: dict[str, float] = inhalt.get("schwellenwerte", {})

    einstellungen = get_settings()
    if modus == "voll" and einstellungen.llm_provider == "fake":
        print("Hinweis: Modus voll mit LLM_PROVIDER=fake ist nur ein Smoke-Test.", file=sys.stderr)

    with httpx.Client(base_url=api_url, timeout=TIMEOUT_SEKUNDEN) as client:
        ergebnisse = evaluiere(inhalt["fragen"], Pruefer(client), modus)

    llm = {"llm_provider": einstellungen.llm_provider, "llm_model": einstellungen.llm_model}
    bericht = erzeuge_bericht(modus, ergebnisse, schwellenwerte, llm, datetime.now().astimezone())
    schreibe_berichte(ausgabe, bericht, schwellenwerte)

    for name, wert in bericht["kennzahlen"].items():
        print(f"{name}: {wert} (Schwellenwert {schwellenwerte.get(name, '-')})")
    for unterschritten in unterschrittene(bericht["kennzahlen"], schwellenwerte):
        print(f"Schwellenwert unterschritten: {unterschritten}", file=sys.stderr)
    return 0 if bericht["bestanden"] else 1


if __name__ == "__main__":
    sys.exit(main())
