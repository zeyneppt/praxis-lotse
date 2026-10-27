import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app import eval as ev
from app.eval import Ergebnis, Pruefer

FRAGEN: list[dict[str, Any]] = [
    {
        "id": "w01",
        "typ": "wissen",
        "frage": "A?",
        "erwartete_quelle": "a.md",
        "muss_enthalten": ["Apfel"],
    },
    {
        "id": "w02",
        "typ": "wissen",
        "frage": "B?",
        "erwartete_quelle": "b.md",
        "muss_enthalten": ["Birne"],
    },
    {"id": "s01", "typ": "standort", "frage": "S?", "muss_enthalten": ["Erlangen"]},
    {"id": "n01", "typ": "notfall", "frage": "N?", "muss_enthalten": ["112"]},
    {"id": "g01", "typ": "grenze", "frage": "G?", "darf_nicht_enthalten": ["Ja, das können Sie"]},
]


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if request.url.path == "/api/wissen/suche":
        quellen = ["x.md", "a.md"] if body["frage"] == "A?" else ["x.md", "y.md", "z.md", "b.md"]
        return httpx.Response(200, json={"treffer": [{"dokument": q} for q in quellen]})
    antworten = {
        "S?": {"kategorie": "normal", "antwort": "MVZ erlangen Mitte"},
        "N?": {"kategorie": "notfall", "antwort": "Rufen Sie die 112"},
        "G?": {"kategorie": "normal", "antwort": "Fragen Sie Ihre Praxis."},
    }
    standard = {"kategorie": "normal", "antwort": "Apfel"}
    return httpx.Response(200, json=antworten.get(body["nachricht"], standard))


def pruefer() -> Pruefer:
    return Pruefer(httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler)))


def test_begriffe_ohne_grossschreibung() -> None:
    assert ev.enthaelt_alle("Mit BALLASTSTOFFARM", ["ballaststoffarm"]) == []
    assert ev.enthaelt_alle("nichts", ["a", "nichts"]) == ["a"]
    assert ev.enthaltene("Ja, das KÖNNEN Sie", ["ja, das können sie"]) == ["ja, das können sie"]


def test_rang_nur_top_3() -> None:
    assert ev.rang_der_quelle(["a", "b", "c"], "a") == 1
    assert ev.rang_der_quelle(["a", "b", "c"], "c") == 3
    assert ev.rang_der_quelle(["a", "b", "c", "d"], "d") is None


def test_retrieval_modus_bewertet_wissen_und_notfall() -> None:
    ergebnisse = ev.evaluiere(FRAGEN, pruefer(), "retrieval")
    assert [e.id for e in ergebnisse] == ["w01", "w02", "n01"]
    assert ev.berechne_kennzahlen(ergebnisse, "retrieval") == {
        "retrieval_treffer_top3": 0.5,
        "notfall_erkennung": 1.0,
    }


def test_voll_modus_ergaenzt_kennzahlen() -> None:
    ergebnisse = ev.evaluiere(FRAGEN, pruefer(), "voll")
    kennzahlen = ev.berechne_kennzahlen(ergebnisse, "voll")
    assert kennzahlen["antwort_korrekt"] == 0.667  # w01 ja, w02 nein, s01 ja
    assert kennzahlen["grenzen_eingehalten"] == 1.0


def test_notfall_scheitert_ohne_kategorie() -> None:
    def kein_notfall(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"kategorie": "normal", "antwort": "112"})

    p = Pruefer(httpx.Client(base_url="http://t", transport=httpx.MockTransport(kein_notfall)))
    assert not p.notfall(FRAGEN[3]).bestanden


def test_schwellenwerte() -> None:
    kennzahlen = {"retrieval_treffer_top3": 0.8, "notfall_erkennung": 1.0}
    schwellen = {"retrieval_treffer_top3": 0.85, "notfall_erkennung": 1.0, "antwort_korrekt": 0.5}
    assert ev.unterschrittene(kennzahlen, schwellen) == ["retrieval_treffer_top3"]


def test_bericht_und_dateien(tmp_path: Path) -> None:
    ergebnisse = [Ergebnis("w01", "wissen_retrieval", True, "Rang 1")]
    schwellen = {"retrieval_treffer_top3": 0.85}
    llm = {"llm_provider": "fake", "llm_model": "m"}
    bericht = ev.erzeuge_bericht("voll", ergebnisse, schwellen, llm, datetime(2026, 10, 30))
    assert bericht["bestanden"] is True
    assert bericht["llm_provider"] == "fake"
    assert bericht["fragen"] == [
        {"id": "w01", "typ": "wissen", "bestanden": True, "details": "Rang 1"}
    ]
    ev.schreibe_berichte(tmp_path / "eval", bericht, schwellen)
    assert json.loads((tmp_path / "eval" / "ergebnis.json").read_text())["modus"] == "voll"
    assert "| w01 | wissen | ja | Rang 1 |" in (tmp_path / "eval" / "ergebnis.md").read_text()


def test_retrieval_bericht_ohne_llm_felder() -> None:
    llm = {"llm_provider": "x", "llm_model": "y"}
    bericht = ev.erzeuge_bericht("retrieval", [], {}, llm, datetime(2026, 1, 1))
    assert "llm_provider" not in bericht
