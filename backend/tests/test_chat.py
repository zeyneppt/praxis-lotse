import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import werkzeuge
from app.api_chat import get_provider, get_sitzungen, get_system_prompt
from app.api_standorte import get_katalog
from app.api_wissen import get_embedder, get_session
from app.chat import (
    FEHLER_ANTWORT,
    KI_HINWEIS,
    LEERE_ANTWORT,
    MAX_WERKZEUGAUFRUFE,
    Quelle,
    extract_quellen,
    load_system_prompt,
    run_chat,
)
from app.llm.base import (
    AssistantMessage,
    LlmError,
    Message,
    ToolCall,
    ToolResult,
    ToolSpec,
    UserMessage,
)
from app.llm.fake import FakeProvider
from app.main import app
from app.sitzungen import SitzungsSpeicher
from app.standorte import Oeffnungszeiten, Standort, StandortKatalog
from app.werkzeuge import WISSEN_K, Werkzeugkasten
from app.wissen import Treffer

ZEITEN = Oeffnungszeiten(mo="8–12", di="8–12", mi="8–12", do="8–12", fr="8–12")


def standort(id: str, ort: str, fachrichtungen: list[str]) -> Standort:
    return Standort(
        id=id,
        name=f"MVZ {ort}",
        ort=ort,
        stadtteil=None,
        adresse="Hauptstraße 1",
        plz="90000",
        telefon="+49 911 0000000",
        fachrichtungen=fachrichtungen,
        oeffnungszeiten=ZEITEN,
        barrierefrei=True,
    )


KATALOG = StandortKatalog(
    [
        standort("std-1", "Erlangen", ["Gastroenterologie"]),
        standort("std-2", "Schwabach", ["Kardiologie"]),
    ]
)


def treffer(dokument: str, titel: str, abschnitt: str = "Abschnitt") -> Treffer:
    return Treffer(dokument=dokument, titel=titel, abschnitt=abschnitt, text="Text", score=0.8)


class FakeEmbedder:
    def embed_passages(self, texts: object) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return [0.0]


@pytest.fixture
def suche(monkeypatch: pytest.MonkeyPatch) -> list[Treffer]:
    """Treffer, die `wissen_suchen` liefert; die Liste kann im Test geändert werden."""
    ergebnis: list[Treffer] = [
        treffer("termin-absagen.md", "Termine verschieben und absagen", "Fristen"),
        treffer("termin-absagen.md", "Termine verschieben und absagen", "Online"),
        treffer("erster-besuch.md", "Ihr erster Besuch"),
    ]

    def fake_search(session: Session, query_embedding: list[float], k: int) -> list[Treffer]:
        assert k == WISSEN_K
        return ergebnis

    monkeypatch.setattr(werkzeuge, "search", fake_search)
    return ergebnis


def kasten() -> Werkzeugkasten:
    return Werkzeugkasten(KATALOG, None, FakeEmbedder())  # type: ignore[arg-type]


def call(name: str, arguments: str, id: str = "c1") -> ToolCall:
    return ToolCall(id=id, name=name, arguments=arguments)


# --- Werkzeuge ---------------------------------------------------------------


def test_werkzeuge_ohne_freie_termine() -> None:
    assert [s.name for s in kasten().specs] == ["standorte_suchen", "wissen_suchen"]


def test_standorte_suchen_liefert_standorte_und_merkt_verzeichnis() -> None:
    k = kasten()
    ergebnis = k.execute(call("standorte_suchen", '{"ort": "erlangen"}'))

    assert not ergebnis.is_error
    inhalt = json.loads(ergebnis.content)
    assert [s["id"] for s in inhalt["standorte"]] == ["std-1"]
    assert inhalt["dokument"] == "standorte.json"
    assert k.gelieferte_dokumente == {"standorte.json": "Standortverzeichnis"}


@pytest.mark.parametrize("argumente", ["", "{}", '{"fachrichtung": null, "ort": null}'])
def test_standorte_suchen_ohne_filter(argumente: str) -> None:
    ergebnis = kasten().execute(call("standorte_suchen", argumente))
    assert len(json.loads(ergebnis.content)["standorte"]) == 2


def test_standorte_suchen_ohne_treffer_ist_keine_quelle() -> None:
    k = kasten()
    ergebnis = k.execute(call("standorte_suchen", '{"fachrichtung": "Akupunktur"}'))

    assert json.loads(ergebnis.content)["standorte"] == []
    assert k.gelieferte_dokumente == {}


def test_wissen_suchen_merkt_jedes_dokument_einmal(suche: list[Treffer]) -> None:
    k = kasten()
    ergebnis = k.execute(call("wissen_suchen", '{"frage": "Absagen?"}'))

    assert [t["abschnitt"] for t in json.loads(ergebnis.content)["treffer"]] == [
        "Fristen",
        "Online",
        "Abschnitt",
    ]
    assert k.gelieferte_dokumente == {
        "termin-absagen.md": "Termine verschieben und absagen",
        "erster-besuch.md": "Ihr erster Besuch",
    }


@pytest.mark.parametrize(
    ("name", "argumente", "meldung"),
    [
        ("termine_buchen", "{}", "Unbekanntes Werkzeug"),
        ("wissen_suchen", "{kein json", "kein gültiges JSON"),
        ("wissen_suchen", '["liste"]', "JSON-Objekt"),
        ("wissen_suchen", "{}", "frage: missing"),
        ("wissen_suchen", '{"frage": "   "}', "frage: string_too_short"),
        ("standorte_suchen", '{"ort": 42}', "ort: string_type"),
    ],
)
def test_ungueltige_werkzeugaufrufe_werden_fehlerergebnisse(
    suche: list[Treffer], name: str, argumente: str, meldung: str
) -> None:
    k = kasten()
    ergebnis = k.execute(call(name, argumente, id="x7"))

    assert ergebnis.is_error
    assert ergebnis.call_id == "x7"
    assert meldung in json.loads(ergebnis.content)["fehler"]
    assert k.gelieferte_dokumente == {}


# --- Quellen -----------------------------------------------------------------

GELIEFERT = {
    "darmspiegelung-vorbereitung.md": "Vorbereitung auf die Darmspiegelung",
    "erster-besuch.md": "Ihr erster Besuch",
    "standorte.json": "Standortverzeichnis",
}


@pytest.mark.parametrize(
    ("antwort", "text", "dokumente"),
    [
        (
            "Leichte Kost.\n\nQuellen: darmspiegelung-vorbereitung.md",
            "Leichte Kost.",
            ["darmspiegelung-vorbereitung.md"],
        ),
        (
            "MVZ Erlangen.\n**Quellen:** `standorte.json`, `erster-besuch.md`",
            "MVZ Erlangen.",
            ["erster-besuch.md", "standorte.json"],
        ),
        ("Siehe oben.\nQuelle: Standortverzeichnis", "Siehe oben.", ["standorte.json"]),
        ("Nichts gefunden.\nQuellen: keine", "Nichts gefunden.", []),
        ("Nichts gefunden.\nQuellen: –", "Nichts gefunden.", []),
        # Ohne Zeile oder mit erfundenem Dokument: alle gelieferten.
        ("Ohne Angabe.", "Ohne Angabe.", list(GELIEFERT)),
        ("Erfunden.\nQuellen: wikipedia.md", "Erfunden.", list(GELIEFERT)),
    ],
)
def test_extract_quellen(antwort: str, text: str, dokumente: list[str]) -> None:
    rest, quellen = extract_quellen(antwort, GELIEFERT)
    assert rest == text
    assert [q.dokument for q in quellen] == dokumente


def test_extract_quellen_nur_gelieferte_dokumente() -> None:
    _, quellen = extract_quellen("x\nQuellen: blutabnahme.md, erster-besuch.md", GELIEFERT)
    assert quellen == [Quelle("erster-besuch.md", "Ihr erster Besuch")]


# --- Chat-Schleife -----------------------------------------------------------


class ScriptedProvider:
    """Gibt vorbereitete Antworten zurück und merkt sich jeden Aufruf."""

    def __init__(self, antworten: list[AssistantMessage]) -> None:
        self._antworten = antworten
        self.aufrufe: list[tuple[list[Message], bool]] = []

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        self.aufrufe.append((list(messages), allow_tools))
        return self._antworten[min(len(self.aufrufe), len(self._antworten)) - 1]

    def check_available(self) -> None:
        return None


def test_fake_provider_nennt_besten_treffer(suche: list[Treffer]) -> None:
    ergebnis = run_chat(FakeProvider(), "system", [], "Wie sage ich ab?", kasten())

    assert ergebnis.antwort == "[Testmodus] Gefunden in: Termine verschieben und absagen"
    assert ergebnis.kategorie == "normal"
    assert ergebnis.quellen == [
        Quelle("termin-absagen.md", "Termine verschieben und absagen"),
        Quelle("erster-besuch.md", "Ihr erster Besuch"),
    ]
    assert ergebnis.werkzeugaufrufe == 1


def test_fake_provider_ohne_treffer(suche: list[Treffer]) -> None:
    suche.clear()
    ergebnis = run_chat(FakeProvider(), "system", [], "Akupunktur?", kasten())

    assert ergebnis.antwort == "[Testmodus] Nichts gefunden"
    assert ergebnis.quellen == []


def test_fake_provider_sucht_mit_der_nutzernachricht(suche: list[Treffer]) -> None:
    verlauf: list[Message] = [UserMessage("Hallo"), AssistantMessage("Hallo!")]
    antwort = FakeProvider().complete("s", [*verlauf, UserMessage("Absagen?")], [])

    assert antwort.tool_calls == [
        ToolCall(id="fake-3", name="wissen_suchen", arguments='{"frage": "Absagen?"}')
    ]


def test_werkzeuglimit_erzwingt_antwort(suche: list[Treffer]) -> None:
    endlos = AssistantMessage("", [call("wissen_suchen", '{"frage": "x"}')])
    provider = ScriptedProvider([endlos] * MAX_WERKZEUGAUFRUFE + [AssistantMessage("Fertig.")])

    ergebnis = run_chat(provider, "s", [], "Frage", kasten())

    assert ergebnis.antwort == "Fertig."
    assert ergebnis.werkzeugaufrufe == MAX_WERKZEUGAUFRUFE
    assert [erlaubt for _, erlaubt in provider.aufrufe] == [True] * 4 + [False]


def test_werkzeugaufrufe_ueber_dem_limit_bekommen_fehlerergebnis(suche: list[Treffer]) -> None:
    viele = AssistantMessage(
        "", [call("wissen_suchen", '{"frage": "x"}', id=f"c{i}") for i in range(6)]
    )
    provider = ScriptedProvider([viele, AssistantMessage("Fertig.")])

    ergebnis = run_chat(provider, "s", [], "Frage", kasten())

    ergebnisse = [m for m in provider.aufrufe[-1][0] if isinstance(m, ToolResult)]
    assert [e.call_id for e in ergebnisse] == [f"c{i}" for i in range(6)]
    assert [e.is_error for e in ergebnisse] == [False] * 4 + [True] * 2
    assert ergebnis.werkzeugaufrufe == 4
    assert provider.aufrufe[-1][1] is False


def test_werkzeugaufrufe_trotz_verbot_werden_ignoriert(suche: list[Treffer]) -> None:
    stur = AssistantMessage("Teilantwort.", [call("wissen_suchen", '{"frage": "x"}')])
    ergebnis = run_chat(ScriptedProvider([stur]), "s", [], "Frage", kasten())

    assert ergebnis.antwort == "Teilantwort."
    assert ergebnis.werkzeugaufrufe == MAX_WERKZEUGAUFRUFE


def test_ungueltiger_werkzeugaufruf_wird_dem_modell_zurueckgegeben() -> None:
    provider = ScriptedProvider(
        [
            AssistantMessage("", [call("gibt_es_nicht", "{")]),
            AssistantMessage("Dazu habe ich nichts gefunden.\nQuellen: keine"),
        ]
    )

    ergebnis = run_chat(provider, "s", [], "Frage", kasten())

    rueckgabe = provider.aufrufe[1][0][-1]
    assert isinstance(rueckgabe, ToolResult) and rueckgabe.is_error
    assert ergebnis.antwort == "Dazu habe ich nichts gefunden."
    assert ergebnis.quellen == []


def test_verlauf_wird_dem_modell_mitgegeben(suche: list[Treffer]) -> None:
    provider = ScriptedProvider([AssistantMessage("Gern.")])
    verlauf: list[Message] = [UserMessage("Schwabach"), AssistantMessage("Ok.")]

    run_chat(provider, "s", verlauf, "Fachrichtungen?", kasten())

    assert provider.aufrufe[0][0] == [*verlauf, UserMessage("Fachrichtungen?")]


def test_antwort_ohne_werkzeug_loest_rueckfallsuche_aus(suche: list[Treffer]) -> None:
    provider = ScriptedProvider(
        [
            AssistantMessage("Aus eigenem Wissen: ja."),
            AssistantMessage("Laut Merkblatt nein.\nQuellen: termin-absagen.md"),
        ]
    )

    ergebnis = run_chat(provider, "s", [], "Darf ich absagen?", kasten())

    zweiter_aufruf = provider.aufrufe[1][0]
    rueckfall = zweiter_aufruf[-2]
    assert isinstance(rueckfall, AssistantMessage)
    assert rueckfall.text == ""  # die Antwort ohne Grundlage geht nicht in den Verlauf
    assert rueckfall.tool_calls[0].name == "wissen_suchen"
    assert json.loads(rueckfall.tool_calls[0].arguments) == {"frage": "Darf ich absagen?"}
    assert isinstance(zweiter_aufruf[-1], ToolResult)
    assert ergebnis.antwort == "Laut Merkblatt nein."
    assert ergebnis.quellen == [Quelle("termin-absagen.md", "Termine verschieben und absagen")]
    assert ergebnis.werkzeugaufrufe == 1


def test_keine_rueckfallsuche_nach_eigenem_werkzeugaufruf(suche: list[Treffer]) -> None:
    provider = ScriptedProvider(
        [
            AssistantMessage("", [call("standorte_suchen", '{"ort": "Schwabach"}')]),
            AssistantMessage("MVZ Schwabach.\nQuellen: standorte.json"),
        ]
    )

    ergebnis = run_chat(provider, "s", [], "Schwabach?", kasten())

    assert len(provider.aufrufe) == 2
    assert [q.dokument for q in ergebnis.quellen] == ["standorte.json"]


def test_leere_antwort_wird_ersetzt(suche: list[Treffer]) -> None:
    ergebnis = run_chat(ScriptedProvider([AssistantMessage("")]), "s", [], "Frage", kasten())
    assert ergebnis.antwort == LEERE_ANTWORT


# --- Sitzungen ---------------------------------------------------------------


class Uhr:
    def __init__(self) -> None:
        self.jetzt = 1000.0

    def __call__(self) -> float:
        return self.jetzt


def test_sitzung_haelt_hoechstens_20_nachrichten() -> None:
    speicher = SitzungsSpeicher()
    for i in range(15):
        speicher.speichern("s", f"frage {i}", f"antwort {i}")

    verlauf = speicher.verlauf("s")
    assert len(verlauf) == 20
    assert verlauf[0] == UserMessage("frage 5")
    assert verlauf[-1] == AssistantMessage("antwort 14")


def test_sitzung_laeuft_nach_30_minuten_inaktivitaet_ab() -> None:
    uhr = Uhr()
    speicher = SitzungsSpeicher(uhr=uhr)
    speicher.speichern("s", "frage", "antwort")

    uhr.jetzt += 29 * 60
    assert len(speicher.verlauf("s")) == 2  # Zugriff verlängert die Sitzung
    uhr.jetzt += 29 * 60
    assert len(speicher.verlauf("s")) == 2
    uhr.jetzt += 30 * 60 + 1
    assert speicher.verlauf("s") == []
    assert len(speicher) == 0


def test_unbekannte_sitzung_hat_leeren_verlauf() -> None:
    assert SitzungsSpeicher().verlauf("neu") == []


# --- Systemprompt ------------------------------------------------------------


def test_systemprompt_enthaelt_pflichtinhalte() -> None:
    prompt = load_system_prompt()
    for teil in [
        "MVZ Musterverbund Franken",
        "Deutsch",
        "120 Wörter",
        "Werkzeugergebnissen",
        "Telefon des Standorts",
        "keine Diagnosen",
        "116117",
        "112",
        "PL-KANARIE-7731",
    ]:
        assert teil in prompt


# --- API ---------------------------------------------------------------------


class FehlerProvider:
    def complete(self, *args: Any, **kwargs: Any) -> AssistantMessage:
        raise LlmError("APITimeoutError")

    def check_available(self) -> None:
        return None


@pytest.fixture
def sitzungen() -> SitzungsSpeicher:
    return SitzungsSpeicher()


@pytest.fixture
def client(suche: list[Treffer], sitzungen: SitzungsSpeicher) -> Iterator[TestClient]:
    app.dependency_overrides[get_katalog] = lambda: KATALOG
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_provider] = FakeProvider
    app.dependency_overrides[get_system_prompt] = lambda: "system"
    app.dependency_overrides[get_sitzungen] = lambda: sitzungen
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_chat_vertrag(client: TestClient) -> None:
    antwort = client.post("/api/chat", json={"nachricht": "Wie sage ich ab?"})

    assert antwort.status_code == 200
    daten = antwort.json()
    assert set(daten) == {"sitzung_id", "antwort", "kategorie", "quellen", "aktion", "ki_hinweis"}
    assert len(daten["sitzung_id"]) == 36
    assert daten["kategorie"] == "normal"
    assert daten["aktion"] is None
    assert daten["ki_hinweis"] == KI_HINWEIS
    assert daten["quellen"][0] == {
        "dokument": "termin-absagen.md",
        "titel": "Termine verschieben und absagen",
    }


def test_api_chat_fuehrt_sitzung_fort(client: TestClient, sitzungen: SitzungsSpeicher) -> None:
    erste = client.post("/api/chat", json={"nachricht": "Hallo"}).json()
    zweite = client.post(
        "/api/chat", json={"nachricht": "Und weiter?", "sitzung_id": erste["sitzung_id"]}
    ).json()
    dritte = client.post("/api/chat", json={"nachricht": "Neu"}).json()

    assert zweite["sitzung_id"] == erste["sitzung_id"]
    assert dritte["sitzung_id"] != erste["sitzung_id"]
    assert len(sitzungen.verlauf(erste["sitzung_id"])) == 4


@pytest.mark.parametrize(
    "body",
    [
        {"nachricht": ""},
        {"nachricht": "   "},
        {"nachricht": "a" * 1001},
        {},
        {"nachricht": "Hallo", "sitzung_id": "keine-uuid"},
    ],
)
def test_api_chat_ungueltige_anfrage(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/api/chat", json=body).status_code == 422


def test_api_chat_erlaubt_1000_zeichen(client: TestClient) -> None:
    assert client.post("/api/chat", json={"nachricht": "a" * 1000}).status_code == 200


def test_api_chat_anbieterfehler_liefert_kategorie_fehler(
    client: TestClient, sitzungen: SitzungsSpeicher
) -> None:
    app.dependency_overrides[get_provider] = FehlerProvider

    antwort = client.post("/api/chat", json={"nachricht": "Hallo"})

    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["kategorie"] == "fehler"
    assert daten["antwort"] == FEHLER_ANTWORT
    assert "anrufen" in daten["antwort"] or "rufen Sie" in daten["antwort"]
    assert daten["quellen"] == []
    assert daten["ki_hinweis"] == KI_HINWEIS
    assert sitzungen.verlauf(daten["sitzung_id"]) == []


def test_api_chat_loggt_keinen_nachrichtentext(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    geheim = "Max Mustermann 01.02.1980"
    with caplog.at_level(logging.INFO):
        client.post("/api/chat", json={"nachricht": geheim})
        app.dependency_overrides[get_provider] = FehlerProvider
        client.post("/api/chat", json={"nachricht": geheim})

    assert "Chat: Nachricht mit 25 Zeichen" in caplog.text
    assert "LLM-Anbieter fehlgeschlagen" in caplog.text
    assert "Mustermann" not in caplog.text
