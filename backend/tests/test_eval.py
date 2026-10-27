import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

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
    ergebnisse, api_fehler = ev.evaluiere(FRAGEN, pruefer(), "retrieval")
    assert api_fehler is None
    assert [e.id for e in ergebnisse] == ["w01", "w02", "n01"]
    assert ev.berechne_kennzahlen(ergebnisse, "retrieval") == {
        "retrieval_treffer_top3": 0.5,
        "notfall_erkennung": 1.0,
    }


def test_voll_modus_ergaenzt_kennzahlen() -> None:
    ergebnisse, _ = ev.evaluiere(FRAGEN, pruefer(), "voll")
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


# --- Kennzahl mit Schwellenwert, aber ohne Messwerte ---


def test_fehlende_kennzahl_mit_schwellenwert_ist_fehler() -> None:
    schwellen = {"retrieval_treffer_top3": 0.85, "notfall_erkennung": 1.0}
    nur_wissen = [Ergebnis("w01", "wissen_retrieval", True, "Rang 1")]
    llm = {"llm_provider": "fake", "llm_model": "m"}
    bericht = ev.erzeuge_bericht("retrieval", nur_wissen, schwellen, llm, datetime(2026, 1, 1))
    assert bericht["bestanden"] is False
    assert bericht["fehler"] == ["Keine Messwerte für Kennzahl notfall_erkennung"]


def test_schwellenwert_fuer_kennzahl_eines_anderen_modus_ist_kein_fehler() -> None:
    assert ev.fehlende_kennzahlen({}, {"antwort_korrekt": 0.5}, "retrieval") == []
    assert ev.fehlende_kennzahlen({}, {"antwort_korrekt": 0.5}, "voll") == ["antwort_korrekt"]


def test_main_endet_mit_exit_1_ohne_messwerte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    datei = tmp_path / "fragen.yaml"
    datei.write_text(
        "schwellenwerte: {notfall_erkennung: 1.0}\n"
        "fragen:\n  - {id: w01, typ: wissen, frage: 'A?', erwartete_quelle: a.md}\n"
    )
    _main_vorbereiten(monkeypatch, tmp_path, datei, handler)
    assert ev.main([]) == 1
    assert "Keine Messwerte für Kennzahl notfall_erkennung" in capsys.readouterr().err
    assert json.loads((tmp_path / "aus" / "ergebnis.json").read_text())["bestanden"] is False


# --- HTTP-Fehler, Retry mit Backoff ---


def antworten_nacheinander(status: list[int]) -> tuple[httpx.Client, list[int]]:
    aufrufe: list[int] = []

    def h(_: httpx.Request) -> httpx.Response:
        code = status[min(len(aufrufe), len(status) - 1)]
        aufrufe.append(code)
        if code == 200:
            return httpx.Response(200, json={"kategorie": "normal", "antwort": "ok"})
        return httpx.Response(code, json={"detail": "x"})

    return httpx.Client(base_url="http://t", transport=httpx.MockTransport(h)), aufrufe


def test_429_wird_mit_backoff_wiederholt() -> None:
    client, aufrufe = antworten_nacheinander([429, 429, 200])
    pausen: list[float] = []
    p = Pruefer(client, warten=pausen.append, backoff_sekunden=2.0)
    assert p.antwort_enthaelt(
        {"id": "s", "typ": "standort", "frage": "x", "muss_enthalten": ["ok"]}
    ).bestanden
    assert aufrufe == [429, 429, 200]
    assert pausen == [2.0, 4.0]


def test_dauerhaftes_429_wirft_api_fehler() -> None:
    client, aufrufe = antworten_nacheinander([429])
    p = Pruefer(client, warten=lambda _: None, max_versuche=3)
    with pytest.raises(ev.ApiFehler, match="HTTP 429 nach 3 Versuchen"):
        p.antwort_enthaelt({"id": "s", "typ": "standort", "frage": "x"})
    assert len(aufrufe) == 3


def test_client_fehler_wird_nicht_wiederholt() -> None:
    client, aufrufe = antworten_nacheinander([422])
    p = Pruefer(client, warten=lambda _: None)
    with pytest.raises(ev.ApiFehler, match="HTTP 422"):
        p.antwort_enthaelt({"id": "s", "typ": "standort", "frage": "x"})
    assert aufrufe == [422]


def test_verbindungsfehler_wird_wiederholt() -> None:
    zaehler = {"n": 0}

    def h(_: httpx.Request) -> httpx.Response:
        zaehler["n"] += 1
        if zaehler["n"] < 2:
            raise httpx.ConnectError("weg")
        return httpx.Response(200, json={"kategorie": "normal", "antwort": "ok"})

    p = Pruefer(
        httpx.Client(base_url="http://t", transport=httpx.MockTransport(h)), warten=lambda _: None
    )
    assert p.antwort_enthaelt({"id": "s", "typ": "standort", "frage": "x"}).bestanden
    assert zaehler["n"] == 2


def test_evaluation_bricht_bei_api_fehler_ab_und_meldet_ihn() -> None:
    client, _ = antworten_nacheinander([429])
    p = Pruefer(client, warten=lambda _: None, max_versuche=2)
    ergebnisse, api_fehler = ev.evaluiere(FRAGEN, p, "retrieval")
    assert api_fehler is not None and "w01" in api_fehler
    assert [(e.id, e.bestanden) for e in ergebnisse] == [("w01", False)]
    assert "API-Fehler" in ergebnisse[0].details
    bericht = ev.erzeuge_bericht("retrieval", ergebnisse, {}, {}, datetime(2026, 1, 1), api_fehler)
    assert bericht["bestanden"] is False
    assert bericht["fehler"] == [api_fehler]


def test_main_schreibt_bericht_und_exit_1_bei_dauerhaftem_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    datei = tmp_path / "fragen.yaml"
    datei.write_text("fragen:\n  - {id: n01, typ: notfall, frage: 'N?', muss_enthalten: ['112']}\n")
    _main_vorbereiten(monkeypatch, tmp_path, datei, lambda _: httpx.Response(429))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    assert ev.main([]) == 1
    assert "HTTP 429" in capsys.readouterr().err
    bericht = json.loads((tmp_path / "aus" / "ergebnis.json").read_text())
    assert bericht["bestanden"] is False
    assert (tmp_path / "aus" / "ergebnis.md").exists()


def _main_vorbereiten(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    datei: Path,
    h: Any,
) -> None:
    monkeypatch.setenv("EVAL_DATEI", str(datei))
    monkeypatch.setenv("EVAL_AUSGABE", str(tmp_path / "aus"))
    monkeypatch.delenv("EVAL_MODUS", raising=False)
    echter_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **_: echter_client(base_url="http://t", transport=httpx.MockTransport(h)),
    )


# --- Modus als Literal ---


def test_modi_kommen_aus_dem_literal() -> None:
    assert ev.MODI == ("retrieval", "voll")


def test_unbekannter_modus_wird_abgelehnt(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        ev.main(["--modus", "schnell"])
    assert exit_info.value.code == 2
    assert "Unbekannter Modus" in capsys.readouterr().err


def test_unbekannter_modus_aus_umgebung_wird_abgelehnt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAL_MODUS", "schnell")
    with pytest.raises(SystemExit):
        ev.main([])
