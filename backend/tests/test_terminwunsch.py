import logging
from datetime import date
from pathlib import Path

import pytest

from app.chat import Quelle, run_chat
from app.leitplanken import texte
from app.leitplanken.terminwunsch import erkenne_terminwunsch, nennt_termin
from app.llm.base import AssistantMessage, Message, ToolCall, ToolSpec, UserMessage
from app.standorte import load_katalog
from app.termine import Anfrage, AnfrageAntwort, Slot, Terminsystem
from app.werkzeuge import MAX_TERMINE, Werkzeugkasten

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
KATALOG = load_katalog(DATA_DIR)
STANDORTVERZEICHNIS = [Quelle("standorte.json", "Standortverzeichnis")]

# --- Erkennung ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("nachricht", "fachrichtung", "ort"),
    [
        (
            "Ich hätte gern einen Termin in der Gastroenterologie in Fürth.",
            "Gastroenterologie",
            "Fürth",
        ),
        ("termin kardiologie schwabach", "Kardiologie", "Schwabach"),
        ("TERMIN GASTROENTEROLOGIE FUERTH", "Gastroenterologie", "Fürth"),
        ("Terminanfrage Gynäkologie Stein", "Gynäkologie", "Stein"),
        ("Termine für Gynaekologie in Erlangen?", "Gynäkologie", "Erlangen"),
        ("Ich suche einen Termin beim Neurologen in Erlangen", "Neurologie", "Erlangen"),
        ("Termin bei einer Kardiologin in Schwabach", "Kardiologie", "Schwabach"),
        ("Termin beim Orthopäden in Zirndorf", "Orthopädie", "Zirndorf"),
        ("Gibt es Termine für Innere Medizin in Lauf?", "Innere Medizin", "Lauf an der Pegnitz"),
        (
            "Termin in der Inneren Medizin in Lauf an der Pegnitz",
            "Innere Medizin",
            "Lauf an der Pegnitz",
        ),
        ("Termin Allgemeinmedizin Nürnberg", "Allgemeinmedizin", "Nürnberg"),
    ],
)
def test_terminwunsch_erkannt(nachricht: str, fachrichtung: str, ort: str) -> None:
    wunsch = erkenne_terminwunsch(nachricht, KATALOG)

    assert wunsch is not None
    assert (wunsch.fachrichtung, wunsch.ort) == (fachrichtung, ort)


@pytest.mark.parametrize(
    "nachricht",
    [
        # Kein Wort mit „termin"
        "Gastroenterologie in Fürth",
        "Wann hat die Gastroenterologie in Fürth geöffnet?",
        # Keine Fachrichtung
        "Was muss ich zum ersten Termin mitbringen?",
        "Ich brauche einen Termin in Fürth",
        # Kein Ort
        "Ich brauche einen Termin in der Kardiologie",
        "Termin Kardiologie in München",
        # Zwei Fachrichtungen
        "Termin für Gastroenterologie oder Endoskopie in Fürth",
        # Zwei Orte
        "Termin Allgemeinmedizin in Stein oder Feucht",
        # Ort nur als Teil eines Wortes
        "Termin Gastroenterologie Fürther Straße",
        "Termin Kardiologie Schwabacher",
        # „Medizin" allein ist keine Innere Medizin
        "Termin Medizin Lauf",
    ],
)
def test_kein_terminwunsch(nachricht: str) -> None:
    assert erkenne_terminwunsch(nachricht, KATALOG) is None


def test_terminwunsch_nennt_standorte_am_ort_und_im_verbund() -> None:
    wunsch = erkenne_terminwunsch("Termin Innere Medizin Nürnberg", KATALOG)

    assert wunsch is not None
    assert [s.id for s in wunsch.am_ort] == ["std-001", "std-003", "std-005"]
    assert [s.id for s in wunsch.im_verbund] == [
        "std-001",
        "std-003",
        "std-005",
        "std-008",
        "std-012",
    ]


@pytest.mark.parametrize(
    ("nachricht", "erwartet"),
    [
        ("Termin", True),
        ("Terminabsage bitte", True),
        ("TERMINE?", True),
        ("Ich möchte absagen", False),
        ("Wann ist der Untersuchungstermin?", False),
    ],
)
def test_nennt_termin(nachricht: str, erwartet: bool) -> None:
    assert nennt_termin(nachricht) is erwartet


# --- Antworten ohne LLM ------------------------------------------------------


def slot(standort_id: str, fachrichtung: str, minute: int) -> Slot:
    beginn = f"2026-11-02T09:{minute:02d}:00+01:00"
    return Slot(
        slot_id=f"{standort_id}|{fachrichtung}|{beginn}",
        standort_id=standort_id,
        standort_name="MVZ",
        fachrichtung=fachrichtung,
        beginn=beginn,
    )


class StubTerminsystem(Terminsystem):
    def __init__(self, anzahl: int = 8) -> None:
        self.anzahl = anzahl
        self.aufrufe: list[tuple[str, str, date | None, int]] = []

    def freie_termine(
        self, standort_id: str, fachrichtung: str, ab_datum: date | None, limit: int
    ) -> list[Slot]:
        self.aufrufe.append((standort_id, fachrichtung, ab_datum, limit))
        return [slot(standort_id, fachrichtung, m) for m in range(min(self.anzahl, limit))]

    def anfrage_stellen(self, anfrage: Anfrage) -> AnfrageAntwort:
        raise AssertionError("Der Chat darf keine Anfrage anlegen")

    def anfrage_abrufen(self, anfrage_id: str) -> AnfrageAntwort | None:
        raise AssertionError("nicht erwartet")

    def alte_anfragen_loeschen(self) -> int:
        raise AssertionError("nicht erwartet")


class KeinLlm:
    def complete(self, *args: object, **kwargs: object) -> AssistantMessage:
        raise AssertionError("Bei einem Terminwunsch darf kein LLM aufgerufen werden")

    def check_available(self) -> None:
        return None


def kasten(terminsystem: Terminsystem) -> Werkzeugkasten:
    return Werkzeugkasten(KATALOG, None, None, terminsystem)  # type: ignore[arg-type]


def test_ein_standort_liefert_termine_ohne_llm() -> None:
    terminsystem = StubTerminsystem()

    ergebnis = run_chat(
        KeinLlm(), "system", [], "Termin Gastroenterologie in Fürth", kasten(terminsystem)
    )

    assert terminsystem.aufrufe == [("std-004", "Gastroenterologie", None, MAX_TERMINE)]
    assert ergebnis.termin_vorschlag == [slot("std-004", "Gastroenterologie", m) for m in range(5)]
    assert ergebnis.kategorie == "normal"
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert ergebnis.werkzeugaufrufe == 0
    assert "MVZ Fürth Zentrum" in ergebnis.antwort
    assert "Gastroenterologie" in ergebnis.antwort
    assert not any(zeichen.isdigit() for zeichen in ergebnis.antwort)


def test_ein_standort_ohne_freie_termine() -> None:
    ergebnis = run_chat(
        KeinLlm(), "system", [], "Termin Kardiologie Schwabach", kasten(StubTerminsystem(0))
    )

    assert ergebnis.termin_vorschlag is None
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert "keine freien Termine" in ergebnis.antwort
    assert "MVZ Schwabach" in ergebnis.antwort


def test_mehrere_standorte_werden_zur_auswahl_genannt() -> None:
    terminsystem = StubTerminsystem()

    ergebnis = run_chat(
        KeinLlm(), "system", [], "Termin Innere Medizin in Nürnberg", kasten(terminsystem)
    )

    assert terminsystem.aufrufe == []
    assert ergebnis.termin_vorschlag is None
    assert ergebnis.kategorie == "normal"
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert "MVZ Nürnberg Mitte, MVZ Nürnberg Süd und MVZ Nürnberg West" in ergebnis.antwort
    assert "MVZ Nürnberg Nord" not in ergebnis.antwort


def test_fachrichtung_nicht_am_ort_nennt_anbieter_im_verbund() -> None:
    terminsystem = StubTerminsystem()

    ergebnis = run_chat(
        KeinLlm(), "system", [], "Termin in der Kardiologie in Fürth", kasten(terminsystem)
    )

    assert terminsystem.aufrufe == []
    assert ergebnis.termin_vorschlag is None
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert "In Fürth bietet kein Standort" in ergebnis.antwort
    assert "MVZ Schwabach" in ergebnis.antwort


def test_notfall_hat_vorrang_vor_terminwunsch() -> None:
    terminsystem = StubTerminsystem()

    ergebnis = run_chat(
        KeinLlm(),
        "system",
        [],
        "Termin Kardiologie Schwabach, ich habe starke Brustschmerzen",
        kasten(terminsystem),
    )

    assert ergebnis.kategorie == "notfall"
    assert ergebnis.termin_vorschlag is None
    assert terminsystem.aufrufe == []


# --- Leitplanke gegen erfundene Termine --------------------------------------


class ErfinderProvider:
    """Ruft nie das Terminwerkzeug auf und erfindet eine Uhrzeit."""

    def __init__(self, text: str, werkzeug: ToolCall | None = None) -> None:
        self.text = text
        self.werkzeug = werkzeug

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        if isinstance(messages[-1], UserMessage):
            # Ohne eigenen Werkzeugaufruf sucht der Server in der Wissensbasis; die
            # Rückfallsuche wird hier durch einen Standortaufruf ersetzt.
            call = self.werkzeug or ToolCall("s1", "standorte_suchen", "{}")
            return AssistantMessage("", [call])
        return AssistantMessage(self.text)

    def check_available(self) -> None:
        return None


@pytest.mark.parametrize(
    "erfunden",
    [
        "Freie Termine: Donnerstag, 2. Februar um 09:00.",
        "Sie können um 9.30 kommen.",
        "Kommen Sie am Montag um 10 Uhr.",
    ],
)
def test_erfundene_uhrzeit_wird_ersetzt(erfunden: str, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    ergebnis = run_chat(
        ErfinderProvider(f"{erfunden}\nQuellen: standorte.json"),
        "system",
        [],
        "Ich hätte gern einen Termin beim Hausarzt",
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == texte.TERMIN_NUR_AUS_TERMINSYSTEM
    assert ergebnis.quellen == []
    assert ergebnis.termin_vorschlag is None
    assert "Leitplanke" in caplog.text
    assert "Hausarzt" not in caplog.text


def test_uhrzeit_ohne_terminwort_bleibt() -> None:
    ergebnis = run_chat(
        ErfinderProvider("Fürth hat ab 08:00 geöffnet."),
        "system",
        [],
        "Wann hat Fürth geöffnet?",
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == "Fürth hat ab 08:00 geöffnet."


def test_uhrzeit_mit_termin_aus_terminsystem_bleibt() -> None:
    argumente = '{"standort_id": "std-004", "fachrichtung": "Gastroenterologie"}'
    ergebnis = run_chat(
        ErfinderProvider("Frei ist 09:00.", ToolCall("t1", "freie_termine_suchen", argumente)),
        "system",
        [],
        "Termin in Fürth bitte",
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == "Frei ist 09:00."
    assert ergebnis.termin_vorschlag is not None


def test_uhrzeit_nach_leerem_terminsystem_wird_ersetzt() -> None:
    argumente = '{"standort_id": "std-004", "fachrichtung": "Gastroenterologie"}'
    ergebnis = run_chat(
        ErfinderProvider("Frei ist 09:00.", ToolCall("t1", "freie_termine_suchen", argumente)),
        "system",
        [],
        "Termin in Fürth bitte",
        kasten(StubTerminsystem(0)),
    )

    assert ergebnis.antwort == texte.TERMIN_NUR_AUS_TERMINSYSTEM
