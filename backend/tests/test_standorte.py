import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api_standorte import get_katalog
from app.main import app
from app.standorte import Oeffnungszeiten, Standort, StandortKatalog, load_katalog, normalize

# Im Repo liegt data/ neben backend/, im Container ist es nach /data gemountet.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

ZEITEN = Oeffnungszeiten(mo="8-12", di="8-12", mi="8-12", do="8-12", fr="8-12")


def standort(standort_id: str, ort: str, *fachrichtungen: str) -> Standort:
    return Standort(
        id=standort_id,
        name=f"MVZ {ort}",
        ort=ort,
        stadtteil=None,
        adresse="Musterweg 1",
        plz="90000",
        telefon="+49 000 0",
        fachrichtungen=list(fachrichtungen),
        oeffnungszeiten=ZEITEN,
        barrierefrei=False,
    )


@pytest.fixture
def katalog() -> StandortKatalog:
    # Absichtlich unsortiert, um die Sortierung nach id zu prüfen.
    return StandortKatalog(
        [
            standort("std-003", "Lauf an der Pegnitz", "Orthopädie"),
            standort("std-001", "Nürnberg", "Gastroenterologie", "Endoskopie"),
            standort("std-002", "Fürth", "Gynäkologie", "Allgemeinmedizin"),
        ]
    )


@pytest.fixture
def client(katalog: StandortKatalog) -> Iterator[TestClient]:
    app.dependency_overrides[get_katalog] = lambda: katalog
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("Gynäkologie", "gynaekologie"),
        ("ORTHOPÄDIE", "orthopaedie"),
        ("Nürnberg", "nuernberg"),
        ("Fußpflege", "fusspflege"),
    ],
)
def test_normalize(eingabe: str, erwartet: str) -> None:
    assert normalize(eingabe) == erwartet


def test_ohne_filter_alle_nach_id_sortiert(katalog: StandortKatalog) -> None:
    assert [s.id for s in katalog.search()] == ["std-001", "std-002", "std-003"]


@pytest.mark.parametrize(
    ("fachrichtung", "erwartet"),
    [
        ("gastro", ["std-001"]),
        ("ENDOSKOPIE", ["std-001"]),
        ("gynaekologie", ["std-002"]),
        ("gynäk", ["std-002"]),
        ("orthopaedie", ["std-003"]),
        ("medizin", ["std-002"]),
        ("Zahnmedizin", []),
        ("", ["std-001", "std-002", "std-003"]),
    ],
)
def test_filter_fachrichtung(
    katalog: StandortKatalog, fachrichtung: str, erwartet: list[str]
) -> None:
    assert [s.id for s in katalog.search(fachrichtung=fachrichtung)] == erwartet


@pytest.mark.parametrize(
    ("ort", "erwartet"),
    [("lauf", ["std-003"]), ("NÜRNBERG", ["std-001"]), ("nuernberg", ["std-001"]), ("Köln", [])],
)
def test_filter_ort(katalog: StandortKatalog, ort: str, erwartet: list[str]) -> None:
    assert [s.id for s in katalog.search(ort=ort)] == erwartet


def test_filter_kombiniert_mit_und(katalog: StandortKatalog) -> None:
    assert [s.id for s in katalog.search(fachrichtung="gastro", ort="nürnberg")] == ["std-001"]
    assert katalog.search(fachrichtung="gastro", ort="fürth") == []


def test_fachrichtungen_eindeutig_und_alphabetisch() -> None:
    katalog = StandortKatalog(
        [
            standort("std-001", "A", "Orthopädie", "Innere Medizin"),
            standort("std-002", "B", "Innere Medizin", "Ärztlicher Notdienst", "Neurologie"),
        ]
    )
    assert katalog.fachrichtungen() == [
        "Ärztlicher Notdienst",
        "Innere Medizin",
        "Neurologie",
        "Orthopädie",
    ]


def test_echte_datendatei_wird_geladen() -> None:
    katalog = load_katalog(DATA_DIR)
    standorte = katalog.search()
    assert len(standorte) == 12
    assert standorte[0].id == "std-001"
    stein = katalog.get("std-006")
    assert stein is not None
    assert stein.stadtteil is None


def test_unbekanntes_feld_in_datendatei_wird_abgelehnt(tmp_path: Path) -> None:
    daten = standort("std-001", "Nürnberg", "Neurologie").model_dump()
    daten["unbekannt"] = 1
    (tmp_path / "standorte.json").write_text(json.dumps({"standorte": [daten]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_katalog(tmp_path)


def test_api_liste_mit_filtern(client: TestClient) -> None:
    antwort = client.get("/api/standorte", params={"fachrichtung": "gynaekologie", "ort": "fürth"})
    assert antwort.status_code == 200
    assert [s["id"] for s in antwort.json()] == ["std-002"]


def test_api_unbekannter_filter_liefert_leere_liste(client: TestClient) -> None:
    antwort = client.get("/api/standorte", params={"fachrichtung": "Zahnmedizin"})
    assert antwort.status_code == 200
    assert antwort.json() == []


def test_api_einzelner_standort_hat_exakt_die_vertragsfelder(client: TestClient) -> None:
    antwort = client.get("/api/standorte/std-001")
    assert antwort.status_code == 200
    assert set(antwort.json()) == {
        "id",
        "name",
        "ort",
        "stadtteil",
        "adresse",
        "plz",
        "telefon",
        "fachrichtungen",
        "oeffnungszeiten",
        "barrierefrei",
    }
    assert set(antwort.json()["oeffnungszeiten"]) == {"mo", "di", "mi", "do", "fr"}


def test_api_unbekannter_standort_liefert_404(client: TestClient) -> None:
    antwort = client.get("/api/standorte/std-999")
    assert antwort.status_code == 404
    assert antwort.json() == {"detail": "Standort nicht gefunden"}


def test_api_fachrichtungen(client: TestClient) -> None:
    antwort = client.get("/api/fachrichtungen")
    assert antwort.status_code == 200
    assert antwort.json() == [
        "Allgemeinmedizin",
        "Endoskopie",
        "Gastroenterologie",
        "Gynäkologie",
        "Orthopädie",
    ]
