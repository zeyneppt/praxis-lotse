import pytest

from app.leitplanken.terminwunsch import (
    AllgemeinerTerminwunsch,
    Terminwunsch,
    erkenne_kurzangabe,
)
from tests.test_terminwunsch import KATALOG, STANDORTVERZEICHNIS
from tests.test_terminwunsch_rueckfrage import chat

# --- Erkennung ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("nachricht", "fachrichtung", "ort", "standort_id"),
    [
        ("Kardiologie Fürth", "Kardiologie", "Fürth", None),
        ("Gastroenterologie in Fürth", "Gastroenterologie", "Fürth", None),
        ("GASTROENTEROLOGIE FUERTH!", "Gastroenterologie", "Fürth", None),
        ("gastroenterologie, fürth.", "Gastroenterologie", "Fürth", None),
        ("Ja, Kardiologie im MVZ Schwabach.", "Kardiologie", "Schwabach", "std-007"),
        ("Neurologie in Nürnberg Süd, bitte", "Neurologie", "Nürnberg", "std-003"),
        ("Gerne beim Neurologen in Erlangen", "Neurologie", "Erlangen", None),
        (
            "Innere Medizin in Lauf an der Pegnitz",
            "Innere Medizin",
            "Lauf an der Pegnitz",
            "std-012",
        ),
        ("Inneren Medizin Lauf", "Innere Medizin", "Lauf an der Pegnitz", "std-012"),
        ("Lieber zur Orthopädie und in Zirndorf", "Orthopädie", "Zirndorf", None),
    ],
)
def test_kurzangabe_mit_ort_ist_terminwunsch(
    nachricht: str, fachrichtung: str, ort: str, standort_id: str | None
) -> None:
    wunsch = erkenne_kurzangabe(nachricht, KATALOG)

    assert isinstance(wunsch, Terminwunsch)
    assert (wunsch.fachrichtung, wunsch.ort) == (fachrichtung, ort)
    assert (wunsch.standort.id if wunsch.standort else None) == standort_id


@pytest.mark.parametrize(
    ("nachricht", "fachrichtung"),
    [
        ("Neurologie bitte", "Neurologie"),
        ("neurologie", "Neurologie"),
        ("Kardiologie?", "Kardiologie"),
        ("Eher die Gynäkologie.", "Gynäkologie"),
        ("Ja, gern zum Orthopäden", "Orthopädie"),
        ("Für die Kardiologie", "Kardiologie"),
        ("FÜR GYNÄKOLOGIE", "Gynäkologie"),
    ],
)
def test_kurzangabe_ohne_ort(nachricht: str, fachrichtung: str) -> None:
    assert erkenne_kurzangabe(nachricht, KATALOG) == AllgemeinerTerminwunsch(
        fachrichtung=fachrichtung
    )


@pytest.mark.parametrize(
    "nachricht", ["Neurologie Fürth Erlangen", "Gynäkologie in Stein und Erlangen"]
)
def test_kurzangabe_mit_mehreren_orten_fragt_nach(nachricht: str) -> None:
    assert erkenne_kurzangabe(nachricht, KATALOG) == AllgemeinerTerminwunsch()


@pytest.mark.parametrize(
    "nachricht",
    [
        "Öffnungszeiten der Kardiologie in Schwabach?",
        "Wo ist die Kardiologie?",
        "Kardiologie Fürth Parkplatz",
        "Kardiologie und Neurologie",
        "Kardiologie oder Neurologie in Erlangen",
        "Kardiologie Fürth oder Erlangen",
        "Fürth",
        "MVZ Schwabach",
        "ja bitte",
        "",
        "!!!",
        "Hat die Gastroenterologie in Fürth heute geöffnet?",
    ],
)
def test_keine_kurzangabe(nachricht: str) -> None:
    assert erkenne_kurzangabe(nachricht, KATALOG) is None


# --- Antworten wie beim Terminwunsch, ohne LLM --------------------------------


@pytest.mark.parametrize(
    ("kurzangabe", "terminwunsch"),
    [
        ("Gastroenterologie in Fürth", "Termin Gastroenterologie in Fürth"),
        ("Kardiologie Fürth", "Termin Kardiologie Fürth"),
        ("Ja, Kardiologie im MVZ Schwabach.", "Termin Kardiologie im MVZ Schwabach"),
        ("Innere Medizin Nürnberg", "Termin Innere Medizin Nürnberg"),
        ("Neurologie bitte", "Ich möchte einen Termin in der Neurologie"),
        ("Kardiologie", "Ich möchte einen Termin in der Kardiologie"),
        ("Neurologie Fürth Erlangen", "Einen Termin für Neurologie in Fürth oder Erlangen"),
    ],
)
def test_antwort_wie_terminwunsch(kurzangabe: str, terminwunsch: str) -> None:
    ergebnis, terminsystem = chat(kurzangabe)
    erwartet, erwartet_terminsystem = chat(terminwunsch)

    assert ergebnis == erwartet
    assert terminsystem.aufrufe == erwartet_terminsystem.aufrufe
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert ergebnis.werkzeugaufrufe == 0


def test_kurzangabe_liefert_termine_des_orts() -> None:
    ergebnis, _ = chat("Gastroenterologie in Fürth")

    assert ergebnis.termin_vorschlag
    assert {(s.standort_id, s.fachrichtung) for s in ergebnis.termin_vorschlag} == {
        ("std-004", "Gastroenterologie")
    }


def test_fachrichtung_nicht_am_ort_nennt_anbieter() -> None:
    ergebnis, terminsystem = chat("Kardiologie Fürth")

    assert terminsystem.aufrufe == []
    assert ergebnis.termin_vorschlag is None
    assert "MVZ Schwabach" in ergebnis.antwort


def test_notfall_hat_vorrang() -> None:
    ergebnis, _ = chat("Kardiologie bitte, ich habe Brustschmerzen")

    assert ergebnis.kategorie == "notfall"


def test_weiteres_wort_geht_an_llm() -> None:
    # KeinLlm schlägt beim ersten LLM-Aufruf fehl.
    with pytest.raises(AssertionError, match="kein LLM"):
        chat("Öffnungszeiten der Kardiologie in Schwabach?")
