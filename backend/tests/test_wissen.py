import logging
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.sql import ClauseElement

from app import api_wissen
from app.api_wissen import get_embedder, get_session
from app.ingest import Bestand, plan_ingest
from app.main import app
from app.wissen import (
    Abschnitt,
    Treffer,
    load_abschnitte,
    parse_dokument,
    score_from_distance,
    search,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODELL = "test-modell"

DOKUMENT = """---
titel: Testdokument
fachrichtungen: [Gastroenterologie, Endoskopie]
stand: 2026-09-01
---

> Fiktives Beispieldokument für eine Demo.

## Erster Abschnitt

Text eins.

Zweiter Absatz.

### Unterüberschrift bleibt im Abschnitt

Mehr Text.

## Zweiter Abschnitt

Text zwei.
"""


def test_parse_dokument_ein_abschnitt_pro_ueberschrift() -> None:
    abschnitte = parse_dokument("test.md", DOKUMENT)

    assert [a.abschnitt for a in abschnitte] == ["Erster Abschnitt", "Zweiter Abschnitt"]
    assert [a.position for a in abschnitte] == [0, 1]
    assert abschnitte[0].text == (
        "Text eins.\n\nZweiter Absatz.\n\n### Unterüberschrift bleibt im Abschnitt\n\nMehr Text."
    )
    assert abschnitte[1].text == "Text zwei."
    assert abschnitte[0].titel == "Testdokument"
    assert abschnitte[0].fachrichtungen == ["Gastroenterologie", "Endoskopie"]


def test_hinweiskasten_wird_nicht_indexiert() -> None:
    for abschnitt in parse_dokument("test.md", DOKUMENT):
        assert "Fiktives Beispieldokument" not in abschnitt.einbettungstext


def test_parse_dokument_mit_windows_zeilenenden() -> None:
    abschnitte = parse_dokument("test.md", DOKUMENT.replace("\n", "\r\n"))
    assert [a.text for a in abschnitte][1] == "Text zwei."


def test_einbettungstext_enthaelt_titel_und_abschnitt() -> None:
    abschnitt = parse_dokument("test.md", DOKUMENT)[1]
    assert abschnitt.einbettungstext == "Testdokument – Zweiter Abschnitt\n\nText zwei."


@pytest.mark.parametrize(
    "inhalt",
    [
        "## Ohne Kopf\n\nText",
        "---\ntitel: Nur Titel\n---\n\n## A\n\nText",
    ],
)
def test_fehlender_oder_unvollstaendiger_kopf_wird_abgelehnt(inhalt: str) -> None:
    with pytest.raises(ValueError):
        parse_dokument("kaputt.md", inhalt)


def test_inhalt_hash_haengt_von_inhalt_und_modell_ab() -> None:
    a, b = parse_dokument("test.md", DOKUMENT)
    assert a.inhalt_hash(MODELL) == a.inhalt_hash(MODELL)
    assert len(a.inhalt_hash(MODELL)) == 64
    assert a.inhalt_hash(MODELL) != b.inhalt_hash(MODELL)
    assert a.inhalt_hash(MODELL) != a.inhalt_hash("anderes-modell")


def test_echte_wissensdokumente() -> None:
    abschnitte = load_abschnitte(DATA_DIR)
    dokumente = {a.dokument for a in abschnitte}
    assert len(dokumente) == 8
    darm = [a for a in abschnitte if a.dokument == "darmspiegelung-vorbereitung.md"]
    assert len(darm) == 5
    assert darm[0].titel == "Vorbereitung auf die Darmspiegelung (Koloskopie)"
    assert all("Fiktives Beispieldokument" not in a.text for a in abschnitte)


def abschnitt(dokument: str, text: str, position: int = 0) -> Abschnitt:
    return Abschnitt(
        dokument=dokument,
        titel="T",
        abschnitt="A",
        position=position,
        text=text,
        fachrichtungen=["alle"],
    )


def test_plan_ingest_leere_datenbank() -> None:
    abschnitte = [abschnitt("a.md", "eins"), abschnitt("a.md", "zwei", 1)]
    plan = plan_ingest([], abschnitte, MODELL)
    assert [a for a, _ in plan.neu] == abschnitte
    assert plan.unveraendert == []
    assert plan.geloescht == []


def test_plan_ingest_ist_idempotent() -> None:
    abschnitte = [abschnitt("a.md", "eins"), abschnitt("b.md", "zwei")]
    bestand = [
        Bestand(id=i, dokument=a.dokument, inhalt_hash=a.inhalt_hash(MODELL))
        for i, a in enumerate(abschnitte, start=1)
    ]
    plan = plan_ingest(bestand, abschnitte, MODELL)
    assert plan.neu == []
    assert [i for i, _ in plan.unveraendert] == [1, 2]
    assert plan.geloescht == []


def test_plan_ingest_geaendert_und_geloescht() -> None:
    alt = [abschnitt("a.md", "eins"), abschnitt("a.md", "zwei", 1), abschnitt("weg.md", "x")]
    bestand = [
        Bestand(id=i, dokument=a.dokument, inhalt_hash=a.inhalt_hash(MODELL))
        for i, a in enumerate(alt, start=1)
    ]
    neu = [abschnitt("a.md", "eins"), abschnitt("a.md", "zwei geändert", 1)]

    plan = plan_ingest(bestand, neu, MODELL)

    assert [a.text for a, _ in plan.neu] == ["zwei geändert"]
    assert [i for i, _ in plan.unveraendert] == [1]
    assert plan.geloescht == [2, 3]


def test_plan_ingest_gleicher_text_in_anderem_dokument_ist_neu() -> None:
    a = abschnitt("a.md", "gleich")
    bestand = [Bestand(id=1, dokument="a.md", inhalt_hash=a.inhalt_hash(MODELL))]
    plan = plan_ingest(bestand, [a, abschnitt("b.md", "gleich")], MODELL)
    assert [x.dokument for x, _ in plan.neu] == ["b.md"]
    assert [i for i, _ in plan.unveraendert] == [1]


def test_plan_ingest_doppelte_abschnitte_im_dokument() -> None:
    a = abschnitt("a.md", "gleich")
    bestand = [Bestand(id=7, dokument="a.md", inhalt_hash=a.inhalt_hash(MODELL))]
    plan = plan_ingest(bestand, [a, abschnitt("a.md", "gleich", 1)], MODELL)
    assert [i for i, _ in plan.unveraendert] == [7]
    assert len(plan.neu) == 1


@pytest.mark.parametrize(
    ("distance", "score"),
    [(0.0, 1.0), (0.2694, 0.731), (0.26951, 0.73), (1.0, 0.0), (1.5, -0.5)],
)
def test_score_aus_kosinus_distanz(distance: float, score: float) -> None:
    assert score_from_distance(distance) == score


class FakeEmbedder:
    def __init__(self) -> None:
        self.anfragen: list[str] = []

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.anfragen.append(text)
        return [1.0]


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def suchaufrufe(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[float], int]]:
    aufrufe: list[tuple[list[float], int]] = []

    def fake_search(session: Session, query_embedding: list[float], k: int) -> list[Treffer]:
        aufrufe.append((query_embedding, k))
        return [
            Treffer(dokument="a.md", titel="T", abschnitt="A", text="x", score=0.9)
            for _ in range(k)
        ]

    monkeypatch.setattr(api_wissen, "search", fake_search)
    return aufrufe


@pytest.fixture
def client(embedder: FakeEmbedder) -> Iterator[TestClient]:
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_session] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_suche_standard_k_ist_3(
    client: TestClient, embedder: FakeEmbedder, suchaufrufe: list[tuple[list[float], int]]
) -> None:
    antwort = client.post("/api/wissen/suche", json={"frage": "Koloskopie"})
    assert antwort.status_code == 200
    assert len(antwort.json()["treffer"]) == 3
    assert set(antwort.json()["treffer"][0]) == {"dokument", "titel", "abschnitt", "text", "score"}
    assert embedder.anfragen == ["Koloskopie"]
    assert suchaufrufe == [([1.0], 3)]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"frage": ""},
        {"frage": "a" * 501},
        {"frage": "Test", "k": 0},
        {"frage": "Test", "k": 11},
        {"frage": None},
    ],
)
def test_api_suche_ungueltige_anfrage(
    client: TestClient, suchaufrufe: list[tuple[list[float], int]], body: dict[str, object]
) -> None:
    assert client.post("/api/wissen/suche", json=body).status_code == 422
    assert suchaufrufe == []


@pytest.mark.parametrize(("frage", "k"), [("a", 1), ("a" * 500, 10)])
def test_api_suche_grenzwerte_erlaubt(
    client: TestClient, suchaufrufe: list[tuple[list[float], int]], frage: str, k: int
) -> None:
    assert client.post("/api/wissen/suche", json={"frage": frage, "k": k}).status_code == 200


class FakeErgebnis:
    def __iter__(self) -> Iterator[object]:
        return iter([])


class FakeSession:
    def execute(self, abfrage: object) -> FakeErgebnis:
        return FakeErgebnis()


def test_suche_loggt_keinen_fragetext(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    app.dependency_overrides[get_session] = lambda: FakeSession()
    geheim = "Maxi Mustermann 01.02.1980 Darmspiegelung"
    with caplog.at_level(logging.DEBUG):
        antwort = client.post("/api/wissen/suche", json={"frage": geheim})
    assert antwort.status_code == 200
    meldungen = [r.getMessage() for r in caplog.records if r.name == "app.wissen"]
    assert meldungen and "0 Treffer" in meldungen[0]
    assert all("Mustermann" not in r.getMessage() for r in caplog.records)


def test_search_begrenzt_treffer_pro_dokument_in_sql() -> None:
    gesehen: list[str] = []

    class MerkSession:
        def execute(self, abfrage: ClauseElement) -> FakeErgebnis:
            gesehen.append(str(abfrage.compile(dialect=postgresql.dialect())))  # type: ignore[no-untyped-call]
            return FakeErgebnis()

    search(MerkSession(), [1.0], 4)  # type: ignore[arg-type]
    sql = gesehen[0]
    assert "row_number() OVER (PARTITION BY wissen_abschnitte.dokument" in sql
    assert "<=>" in sql
