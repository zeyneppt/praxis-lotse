import logging
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from app.api_termine import get_termine_ratenbegrenzer, get_terminsystem
from app.logging import redact
from app.main import app
from app.ratenbegrenzung import LIMIT_MELDUNG, Ratenbegrenzer
from app.standorte import load_katalog
from app.termine import (
    ZEITZONE,
    Anfrage,
    FachrichtungUngueltig,
    SimuliertesTerminsystem,
    StandortUnbekannt,
    TerminNichtVerfuegbar,
)
from app.termine.simuliert import (
    Base,
    ist_belegt,
    parse_oeffnungszeiten,
    resolve_fachrichtung,
    slot_id,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
KATALOG = load_katalog(DATA_DIR)

# Dienstag; std-004 ist Mo–Do 07:30–15:00 und Fr 07:30–12:00 geöffnet.
START = datetime(2026, 10, 27, 9, 10, tzinfo=ZEITZONE)


class Uhr:
    def __init__(self, jetzt: datetime) -> None:
        self.jetzt = jetzt

    def __call__(self) -> datetime:
        return self.jetzt


@pytest.fixture
def engine() -> Engine:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def uhr() -> Uhr:
    return Uhr(START)


@pytest.fixture
def system(engine: Engine, uhr: Uhr) -> SimuliertesTerminsystem:
    return SimuliertesTerminsystem(KATALOG, engine, jetzt=uhr)


def anfrage(slot: str, **felder: Any) -> Anfrage:
    daten: dict[str, Any] = {
        "slot_id": slot,
        "name": "Erika Mustermann",
        "geburtsdatum": "1970-05-14",
        "telefon": "+49 170 0000000",
        "einwilligung_datenschutz": True,
    }
    return Anfrage.model_validate(daten | felder)


def minuten(beginn: datetime) -> int:
    return beginn.hour * 60 + beginn.minute


# --- Öffnungszeiten und Raster ----------------------------------------------


def test_parse_oeffnungszeiten_mit_geteilten_intervallen() -> None:
    assert parse_oeffnungszeiten("14:00-18:00, 08:00-12:00") == [
        (time(8), time(12)),
        (time(14), time(18)),
    ]
    assert parse_oeffnungszeiten("07:30–15:00") == [(time(7, 30), time(15))]


@pytest.mark.parametrize("text", ["geschlossen", "8-12", "12:00-08:00", ""])
def test_parse_oeffnungszeiten_lehnt_unlesbares_ab(text: str) -> None:
    with pytest.raises(ValueError):
        parse_oeffnungszeiten(text)


def test_slots_liegen_im_raster_innerhalb_der_oeffnungszeiten(
    system: SimuliertesTerminsystem,
) -> None:
    slots = system.freie_termine("std-004", "Endoskopie", None, 50)

    assert len(slots) == 50
    beginne = [datetime.fromisoformat(s.beginn) for s in slots]
    assert beginne == sorted(beginne)
    for beginn in beginne:
        assert beginn > START
        assert beginn.weekday() < 5
        assert beginn.minute in (0, 30) and beginn.second == 0
        letzter = 11 * 60 + 30 if beginn.weekday() == 4 else 14 * 60 + 30
        assert 7 * 60 + 30 <= minuten(beginn) <= letzter


def test_alle_freien_termine_liegen_in_14_tagen_ab_heute(system: SimuliertesTerminsystem) -> None:
    slots = system.freie_termine("std-001", "Innere Medizin", None, 50)
    slots += system.freie_termine("std-001", "Innere Medizin", date(2026, 11, 3), 50)
    slots += system.freie_termine("std-001", "Innere Medizin", date(2026, 11, 6), 50)

    tage = {datetime.fromisoformat(s.beginn).date() for s in slots}
    assert min(tage) == date(2026, 10, 27)
    assert max(tage) == date(2026, 11, 9)  # heute + 13 Tage, ein Montag
    assert system.freie_termine("std-001", "Innere Medizin", date(2026, 11, 10), 50) == []


def test_geteilte_oeffnungszeiten_haben_mittagspause(system: SimuliertesTerminsystem) -> None:
    slots = []
    for tag in range(14):
        ab = START.date() + timedelta(days=tag)
        slots += system.freie_termine("std-002", "Gynäkologie", ab, 50)

    beginne = {datetime.fromisoformat(s.beginn) for s in slots}
    zeiten = {minuten(b) for b in beginne}
    assert not any(12 * 60 <= m < 14 * 60 for m in zeiten)
    assert max(zeiten) == 17 * 60 + 30
    # Mittwoch und Freitag nur vormittags.
    assert all(minuten(b) < 12 * 60 for b in beginne if b.weekday() in (2, 4))


def test_slot_id_und_beginn_mit_berliner_offset(system: SimuliertesTerminsystem) -> None:
    slot = system.freie_termine("std-004", "gastroenterologie", None, 1)[0]

    assert slot.standort_name == "MVZ Fürth Zentrum"
    assert slot.fachrichtung == "Gastroenterologie"
    assert slot.beginn.endswith("+01:00")
    assert slot.slot_id == f"std-004|Gastroenterologie|{slot.beginn}"


def test_sommerzeit_wechsel(engine: Engine) -> None:
    # Umstellung auf Sommerzeit am Sonntag, 28.03.2027.
    system = SimuliertesTerminsystem(
        KATALOG, engine, jetzt=Uhr(datetime(2027, 3, 25, 6, 0, tzinfo=ZEITZONE))
    )
    slots = system.freie_termine("std-001", "Innere Medizin", date(2027, 3, 26), 50)

    offsets = {(s.beginn[:10], s.beginn[-6:]) for s in slots}
    assert ("2027-03-26", "+01:00") in offsets
    assert ("2027-03-29", "+02:00") in offsets
    assert all(datetime.fromisoformat(s.beginn).hour >= 7 for s in slots)


def test_etwa_die_haelfte_ist_belegt_und_wird_nie_angeboten(
    system: SimuliertesTerminsystem,
) -> None:
    alle = list(system._beginne(KATALOG.get("std-004"), START.date()))  # type: ignore[arg-type]
    belegt = [b for b in alle if ist_belegt("std-004", "Gastroenterologie", b)]
    assert 0.35 < len(belegt) / len(alle) < 0.65

    angeboten = []
    for tag in range(14):
        ab = START.date() + timedelta(days=tag)
        angeboten += system.freie_termine("std-004", "Gastroenterologie", ab, 50)
    angebotene_ids = {s.slot_id for s in angeboten}
    assert angebotene_ids
    assert not angebotene_ids & {slot_id("std-004", "Gastroenterologie", b) for b in belegt}


def test_belegung_ist_stabil() -> None:
    beginn = datetime(2026, 10, 27, 9, 30, tzinfo=ZEITZONE)
    ergebnisse = {ist_belegt("std-004", "Gastroenterologie", beginn) for _ in range(3)}
    assert len(ergebnisse) == 1


# --- Standort und Fachrichtung -----------------------------------------------


def test_unbekannter_standort(system: SimuliertesTerminsystem) -> None:
    with pytest.raises(StandortUnbekannt):
        system.freie_termine("std-999", "Gastroenterologie", None, 10)


@pytest.mark.parametrize(
    ("standort_id", "fachrichtung", "erwartet"),
    [
        ("std-002", "gynaekologie", "Gynäkologie"),
        ("std-002", "GYNÄKOLOGIE", "Gynäkologie"),
        ("std-001", "innere", "Innere Medizin"),
    ],
)
def test_fachrichtung_wie_standortsuche(
    system: SimuliertesTerminsystem, standort_id: str, fachrichtung: str, erwartet: str
) -> None:
    slots = system.freie_termine(standort_id, fachrichtung, None, 1)
    assert slots[0].fachrichtung == erwartet


@pytest.mark.parametrize(
    ("standort_id", "fachrichtung"),
    [("std-004", "Neurologie"), ("std-005", "medizin"), ("std-004", "  ")],
)
def test_fachrichtung_muss_eindeutig_passen(
    system: SimuliertesTerminsystem, standort_id: str, fachrichtung: str
) -> None:
    with pytest.raises(FachrichtungUngueltig):
        system.freie_termine(standort_id, fachrichtung, None, 10)


# --- Anfragen ----------------------------------------------------------------


def test_anfrage_belegt_den_termin(system: SimuliertesTerminsystem) -> None:
    slot = system.freie_termine("std-009", "Neurologie", None, 1)[0]

    antwort = system.anfrage_stellen(anfrage(slot.slot_id))

    assert antwort.status == "angefragt"
    assert antwort.slot == slot
    frei = system.freie_termine("std-009", "Neurologie", None, 50)
    assert slot.slot_id not in {s.slot_id for s in frei}
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(anfrage(slot.slot_id, name="Max Muster"))


def test_anfrage_abrufen(system: SimuliertesTerminsystem) -> None:
    slot = system.freie_termine("std-009", "Neurologie", None, 1)[0]
    angelegt = system.anfrage_stellen(anfrage(slot.slot_id))

    assert system.anfrage_abrufen(angelegt.anfrage_id) == angelegt
    assert system.anfrage_abrufen("00000000-0000-0000-0000-000000000000") is None
    assert system.anfrage_abrufen("keine-uuid") is None


def test_vergangener_termin_ist_nicht_frei(system: SimuliertesTerminsystem, uhr: Uhr) -> None:
    slot = system.freie_termine("std-004", "Gastroenterologie", None, 1)[0]
    uhr.jetzt = datetime.fromisoformat(slot.beginn)

    assert slot.slot_id not in {
        s.slot_id for s in system.freie_termine("std-004", "Gastroenterologie", None, 50)
    }
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(anfrage(slot.slot_id))


def test_belegter_termin_kann_nicht_angefragt_werden(system: SimuliertesTerminsystem) -> None:
    alle = system._beginne(KATALOG.get("std-004"), START.date())  # type: ignore[arg-type]
    belegt = next(b for b in alle if b > START and ist_belegt("std-004", "Gastroenterologie", b))
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(anfrage(slot_id("std-004", "Gastroenterologie", belegt)))


@pytest.mark.parametrize(
    "falsch",
    [
        "std-004|Gastroenterologie|2020-01-06T09:00:00+01:00",
        "std-004|Gastroenterologie|2026-10-28T09:15:00+01:00",
        "std-004|Gastroenterologie|2026-10-28T06:00:00+01:00",
        "std-004|Gastroenterologie|2026-10-31T09:00:00+01:00",
        "std-004|Gastroenterologie|2026-12-01T09:00:00+01:00",
        "std-004|Gastroenterologie|2026-10-28T09:00:00",
        "std-004|Neurologie|2026-10-28T09:00:00+01:00",
        "std-999|Gastroenterologie|2026-10-28T09:00:00+01:00",
        "std-004|Gastroenterologie",
        "Unsinn",
    ],
)
def test_erfundene_slot_ids_sind_nicht_verfuegbar(
    system: SimuliertesTerminsystem, falsch: str
) -> None:
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(anfrage(falsch))


def test_nur_kanonische_slot_id(system: SimuliertesTerminsystem) -> None:
    slot = system.freie_termine("std-004", "Gastroenterologie", None, 1)[0]
    beginn = datetime.fromisoformat(slot.beginn)
    utc = slot.slot_id.replace(
        slot.beginn, beginn.astimezone(ZEITZONE).strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    )
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(anfrage(utc))
    with pytest.raises(TerminNichtVerfuegbar):
        system.anfrage_stellen(
            anfrage(slot.slot_id.replace("Gastroenterologie", "gastroenterologie"))
        )


def test_loeschfrist_30_tage(system: SimuliertesTerminsystem, uhr: Uhr) -> None:
    slot = system.freie_termine("std-009", "Neurologie", None, 1)[0]
    angelegt = system.anfrage_stellen(anfrage(slot.slot_id))

    uhr.jetzt = START + timedelta(days=29, hours=23)
    assert system.alte_anfragen_loeschen() == 0
    assert system.anfrage_abrufen(angelegt.anfrage_id) is not None

    uhr.jetzt = START + timedelta(days=30, minutes=1)
    assert system.alte_anfragen_loeschen() == 1
    assert system.anfrage_abrufen(angelegt.anfrage_id) is None


# --- Validierung der Anfrage -------------------------------------------------


@pytest.mark.parametrize(
    "felder",
    [
        {"name": "E"},
        {"name": "  E  "},
        {"name": "x" * 101},
        {"geburtsdatum": "2099-01-01"},
        {"geburtsdatum": date.today().isoformat()},
        {"geburtsdatum": "1970-02-30"},
        {"telefon": "bitte anrufen"},
        {"telefon": "12345"},
        {"telefon": "1" * 31},
        {"telefon": "0911 123456 ext"},
        {"telefon": "      "},
        {"telefon": "++++++"},
        {"telefon": "-/-/-/"},
        {"telefon": "1 2 3 4 5"},
        {"telefon": "+49 / 1-2-3"},
        {"einwilligung_datenschutz": False},
        {"einwilligung_datenschutz": "true"},
        {"einwilligung_datenschutz": 1},
        {"einwilligung_datenschutz": None},
    ],
)
def test_ungueltige_anfrage(felder: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        anfrage("std-004|Gastroenterologie|2026-10-28T09:00:00+01:00", **felder)


@pytest.mark.parametrize(
    "felder",
    [
        {"name": "Al"},
        {"name": "x" * 100},
        {"telefon": "0911/123-45"},
        {"telefon": "1" * 30},
        {"telefon": "123456"},
        {"telefon": "1 2 3 4 5 6"},
        {"telefon": "+4 9-1/2 3 4"},
    ],
)
def test_gueltige_grenzwerte(felder: dict[str, Any]) -> None:
    anfrage("std-004|Gastroenterologie|2026-10-28T09:00:00+01:00", **felder)


# --- API ---------------------------------------------------------------------


@pytest.fixture
def client(system: SimuliertesTerminsystem) -> Iterator[TestClient]:
    app.dependency_overrides[get_terminsystem] = lambda: system
    begrenzer = Ratenbegrenzer(limit=1000)
    app.dependency_overrides[get_termine_ratenbegrenzer] = lambda: begrenzer
    yield TestClient(app)
    app.dependency_overrides.clear()


def body(slot: str, **felder: Any) -> dict[str, Any]:
    return {
        "slot_id": slot,
        "name": "Erika Mustermann",
        "geburtsdatum": "1970-05-14",
        "telefon": "+49 170 0000000",
        "einwilligung_datenschutz": True,
    } | felder


def test_api_freie_termine(client: TestClient) -> None:
    antwort = client.get(
        "/api/termine/freie", params={"standort_id": "std-004", "fachrichtung": "gastroenterologie"}
    )

    assert antwort.status_code == 200
    slots = antwort.json()
    assert len(slots) == 10
    assert set(slots[0]) == {"slot_id", "standort_id", "standort_name", "fachrichtung", "beginn"}


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"standort_id": "std-999", "fachrichtung": "Gastroenterologie"}, 404),
        ({"standort_id": "std-004", "fachrichtung": "Neurologie"}, 422),
        ({"standort_id": "std-004"}, 422),
        ({"standort_id": "std-004", "fachrichtung": "Endoskopie", "limit": 0}, 422),
        ({"standort_id": "std-004", "fachrichtung": "Endoskopie", "limit": 51}, 422),
        ({"standort_id": "std-004", "fachrichtung": "Endoskopie", "ab_datum": "27.10.2026"}, 422),
        ({"standort_id": "std-004", "fachrichtung": "Endoskopie", "limit": 50}, 200),
        ({"standort_id": "std-004", "fachrichtung": "Endoskopie", "ab_datum": "2026-11-02"}, 200),
    ],
)
def test_api_freie_termine_status(client: TestClient, params: dict[str, Any], status: int) -> None:
    assert client.get("/api/termine/freie", params=params).status_code == status


def test_api_ab_datum(client: TestClient) -> None:
    params = {"standort_id": "std-004", "fachrichtung": "Endoskopie", "ab_datum": "2026-11-02"}
    slots = client.get("/api/termine/freie", params=params).json()
    assert slots[0]["beginn"].startswith("2026-11-02T")


def test_api_anfrage_ohne_personenbezogene_daten(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    slot = client.get(
        "/api/termine/freie", params={"standort_id": "std-009", "fachrichtung": "Neurologie"}
    ).json()[0]

    with caplog.at_level(logging.INFO):
        angelegt = client.post("/api/termine/anfragen", json=body(slot["slot_id"]))
        doppelt = client.post("/api/termine/anfragen", json=body(slot["slot_id"]))
        abruf = client.get(f"/api/termine/anfragen/{angelegt.json()['anfrage_id']}")

    assert angelegt.status_code == 201
    assert set(angelegt.json()) == {"anfrage_id", "status", "slot"}
    assert angelegt.json()["slot"] == slot
    assert doppelt.status_code == 409
    assert doppelt.json() == {"detail": "Termin nicht mehr verfügbar"}
    assert abruf.status_code == 200
    assert abruf.json() == angelegt.json()
    for text in (angelegt.text, abruf.text, caplog.text):
        assert "Mustermann" not in text
        assert "1970-05-14" not in text
        assert "170 0000000" not in text
    assert f"anfrage_id={angelegt.json()['anfrage_id']}" in caplog.text
    # Alle Logs laufen durch redact(): das Datum im Slot ist dort ein Platzhalter.
    assert redact(slot["slot_id"]) in caplog.text


@pytest.mark.parametrize(
    "felder",
    [{"einwilligung_datenschutz": False}, {"telefon": "bitte anrufen"}, {"name": None}],
)
def test_api_anfrage_ungueltig(client: TestClient, felder: dict[str, Any]) -> None:
    antwort = client.post(
        "/api/termine/anfragen", json=body("std-004|Gastroenterologie|x", **felder)
    )
    assert antwort.status_code == 422


@pytest.mark.parametrize("anfrage_id", ["00000000-0000-0000-0000-000000000000", "keine-uuid"])
def test_api_unbekannte_anfrage(client: TestClient, anfrage_id: str) -> None:
    assert client.get(f"/api/termine/anfragen/{anfrage_id}").status_code == 404


def test_api_abgelehnte_slot_id_landet_nicht_im_log(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    manipuliert = "Erika Mustermann 0170\nINFO: gefälschte Zeile"

    with caplog.at_level(logging.INFO):
        antwort = client.post("/api/termine/anfragen", json=body(manipuliert))

    assert antwort.status_code == 409
    assert "Terminanfrage abgelehnt" in caplog.text
    assert "Mustermann" not in caplog.text
    assert "gefälschte Zeile" not in caplog.text


def test_exakte_fachrichtung_gewinnt(engine: Engine) -> None:
    standort = KATALOG.get("std-001")
    assert standort is not None
    erweitert = standort.model_copy(
        update={"fachrichtungen": ["Innere Medizin", "Innere Medizin – Kardiologie"]}
    )
    assert resolve_fachrichtung(erweitert, "innere medizin") == "Innere Medizin"
    with pytest.raises(FachrichtungUngueltig):
        resolve_fachrichtung(erweitert, "innere")


def test_api_422_wiederholt_keine_personenbezogenen_daten(client: TestClient) -> None:
    antworten = [
        client.post("/api/termine/anfragen", json=body("x", telefon="bitte 0911 anrufen")),
        client.post("/api/termine/anfragen", json=body("x", geburtsdatum="2099-01-01")),
        client.post("/api/termine/anfragen", json=body("x", name="E")),
        client.post("/api/termine/anfragen", json=body("x", name="Erika Mustermann" * 10)),
        client.post("/api/termine/anfragen", json={"name": "Erika Mustermann"}),
    ]

    for antwort in antworten:
        assert antwort.status_code == 422
        fehler = antwort.json()["detail"]
        assert fehler and all(set(e) == {"loc", "msg", "type"} for e in fehler)
        for geheim in ("0911", "2099-01-01", "Mustermann", '"E"'):
            assert geheim not in antwort.text


def test_api_telefon_ohne_genug_ziffern(client: TestClient) -> None:
    antwort = client.post("/api/termine/anfragen", json=body("x", telefon="+ 12 - 34 /"))

    assert antwort.status_code == 422
    assert antwort.json()["detail"][0]["loc"] == ["body", "telefon"]
    assert "mindestens 6 Ziffern" in antwort.json()["detail"][0]["msg"]


def test_api_anfrage_wird_begrenzt(client: TestClient) -> None:
    begrenzer = Ratenbegrenzer(limit=2)
    app.dependency_overrides[get_termine_ratenbegrenzer] = lambda: begrenzer
    # Ungültige Anfragen (422) zählen mit: Das Limit gilt für jeden Aufruf des Endpunkts.
    codes = [client.post("/api/termine/anfragen", json={}).status_code for _ in range(3)]

    assert codes == [422, 422, 429]
    antwort = client.post("/api/termine/anfragen", json={})
    assert antwort.json() == {"detail": LIMIT_MELDUNG}
