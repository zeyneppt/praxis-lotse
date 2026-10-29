import re

import pytest

from app.chat import ChatErgebnis, run_chat
from app.leitplanken import texte
from app.leitplanken.terminwunsch import AllgemeinerTerminwunsch, erkenne_allgemeinen_terminwunsch
from app.werkzeuge import MAX_TERMINE
from tests.test_terminwunsch import (
    KATALOG,
    STANDORTVERZEICHNIS,
    KeinLlm,
    StubTerminsystem,
    kasten,
    slot,
)

ALLE_FACHRICHTUNGEN = KATALOG.fachrichtungen()

# --- Erkennung ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("nachricht", "erwartet"),
    [
        ("Welche freien Termine gibt es bei Ihnen?", AllgemeinerTerminwunsch()),
        ("Ich möchte einen Termin", AllgemeinerTerminwunsch()),
        ("Kann ich online einen Termin buchen?", AllgemeinerTerminwunsch()),
        ("Wo kann ich Termine vereinbaren?", AllgemeinerTerminwunsch()),
        ("Gibt es noch FREIE TERMINE?", AllgemeinerTerminwunsch()),
        ("Ich brauche einen Untersuchungstermin", AllgemeinerTerminwunsch()),
        ("Ich möchte einen Termin in Fürth", AllgemeinerTerminwunsch(ort="Fürth")),
        ("freie termine fuerth", AllgemeinerTerminwunsch(ort="Fürth")),
        ("Einen Termin in Stein, bitte", AllgemeinerTerminwunsch(ort="Stein")),
        (
            "Ich brauche einen Termin in der Kardiologie",
            AllgemeinerTerminwunsch(fachrichtung="Kardiologie"),
        ),
        (
            "Kann ich einen Termin beim Neurologen vereinbaren?",
            AllgemeinerTerminwunsch(fachrichtung="Neurologie"),
        ),
        # Unbekannter Ort zählt nicht als Ort.
        (
            "Einen Termin Kardiologie in München",
            AllgemeinerTerminwunsch(fachrichtung="Kardiologie"),
        ),
        # Mehrdeutig → allgemeine Rückfrage
        ("Einen Termin für Kardiologie oder Neurologie", AllgemeinerTerminwunsch()),
        ("Einen Termin in Fürth oder Stein", AllgemeinerTerminwunsch()),
        ("Einen Termin im MVZ Nürnberg Süd oder MVZ Stein", AllgemeinerTerminwunsch()),
        ("Einen Termin für Kardiologie in Fürth oder Stein", AllgemeinerTerminwunsch()),
        ("Einen Termin Gastroenterologie oder Endoskopie in Fürth", AllgemeinerTerminwunsch()),
    ],
)
def test_allgemeiner_terminwunsch_erkannt(
    nachricht: str, erwartet: AllgemeinerTerminwunsch
) -> None:
    assert erkenne_allgemeinen_terminwunsch(nachricht, KATALOG) == erwartet


@pytest.mark.parametrize(
    ("nachricht", "standort_id"),
    [
        ("Einen Termin im MVZ Nürnberg Süd", "std-003"),
        # „MVZ Lauf" → „Lauf" ist ein Standortname, nicht der Ort „Lauf an der Pegnitz" (wie 009).
        ("Einen Termin in Lauf, bitte", "std-012"),
    ],
)
def test_genannter_standort_ohne_fachrichtung(nachricht: str, standort_id: str) -> None:
    wunsch = erkenne_allgemeinen_terminwunsch(nachricht, KATALOG)

    assert wunsch is not None
    assert wunsch.standort is not None
    assert wunsch.standort.id == standort_id
    assert (wunsch.fachrichtung, wunsch.ort) == (None, None)


@pytest.mark.parametrize(
    "nachricht",
    [
        # Kein Wort mit „termin"
        "Welche Fachrichtungen gibt es in Fürth?",
        "Ich möchte einen Arzt in Fürth",
        "Ist noch etwas frei?",
        # Kein Wunschwort
        "Termin in Fürth bitte",
        "Wann ist mein Termin?",
        "Ich hätte gern Termine beim Hausarzt",
        "Was kostet ein Termin?",
        # Wunschwort muss am Wortanfang stehen (Spec 010, Anforderung 2)
        "Terminbuchung bitte",
        # Vollständiger Terminwunsch: Spec 009 ist zuständig
        "Ich hätte gern einen Termin in der Gastroenterologie in Fürth.",
        "Einen Termin Innere Medizin im MVZ Nürnberg Süd",
    ],
)
def test_kein_allgemeiner_terminwunsch(nachricht: str) -> None:
    assert erkenne_allgemeinen_terminwunsch(nachricht, KATALOG) is None


@pytest.mark.parametrize(
    "nachricht",
    [
        "Ich möchte meinen Termin absagen",
        "Wie lange vorher muss ich einen Termin absagen?",
        "Kann ich einen Termin verschieben?",
        "Ich möchte einen Termin stornieren",
        "Was muss ich zum ersten Termin mitbringen, wenn ich einen Termin habe?",
        "Einen freien Termin in Fürth absagen",
    ],
)
def test_ausschlusswoerter(nachricht: str) -> None:
    assert erkenne_allgemeinen_terminwunsch(nachricht, KATALOG) is None


# --- Antworten ohne LLM ------------------------------------------------------


def chat(
    nachricht: str, terminsystem: StubTerminsystem | None = None
) -> tuple[ChatErgebnis, StubTerminsystem]:
    terminsystem = terminsystem or StubTerminsystem()
    return run_chat(KeinLlm(), "system", [], nachricht, kasten(terminsystem)), terminsystem


def assert_regelbasiert_ohne_aktion(ergebnis: ChatErgebnis, terminsystem: StubTerminsystem) -> None:
    assert ergebnis.kategorie == "normal"
    assert ergebnis.termin_vorschlag is None
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert ergebnis.werkzeugaufrufe == 0
    assert terminsystem.aufrufe == []
    assert not re.search(r"\b\d{1,2}[:.]\d{2}\b", ergebnis.antwort)


def test_ohne_angaben_rueckfrage_mit_allen_fachrichtungen() -> None:
    ergebnis, terminsystem = chat("Welche freien Termine gibt es bei Ihnen?")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    assert ergebnis.antwort == texte.TERMINWUNSCH_RUECKFRAGE.format(
        fachrichtungen=", ".join(ALLE_FACHRICHTUNGEN[:-1]) + f" und {ALLE_FACHRICHTUNGEN[-1]}"
    )
    for fachrichtung in ALLE_FACHRICHTUNGEN:
        assert fachrichtung in ergebnis.antwort
    assert "„Termin Gastroenterologie in Fürth" in ergebnis.antwort


def test_mehrdeutig_rueckfrage() -> None:
    ergebnis, terminsystem = chat("Einen Termin für Kardiologie oder Neurologie")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    assert ergebnis.antwort.startswith("Gern suche ich freie Termine")


def test_nur_ort_nennt_fachrichtungen_dort() -> None:
    ergebnis, terminsystem = chat("Ich möchte einen Termin in Fürth")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    assert ergebnis.antwort == (
        "In Fürth gibt es im Verbund diese Fachrichtungen: Endoskopie und Gastroenterologie. "
        'Bitte nennen Sie die Fachrichtung, zum Beispiel: „Termin Endoskopie in Fürth".'
    )


def test_ort_mit_mehreren_standorten_nennt_alle_fachrichtungen_dort() -> None:
    ergebnis, terminsystem = chat("Einen Termin in Nürnberg bitte")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    am_ort = {f for s in KATALOG.search() if s.ort == "Nürnberg" for f in s.fachrichtungen}
    for fachrichtung in ALLE_FACHRICHTUNGEN:
        assert (fachrichtung in ergebnis.antwort) == (fachrichtung in am_ort)


def test_nur_standort_nennt_seine_fachrichtungen() -> None:
    ergebnis, terminsystem = chat("Einen Termin im MVZ Nürnberg Süd")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    assert ergebnis.antwort == (
        "Im MVZ Nürnberg Süd gibt es diese Fachrichtungen: Innere Medizin und Neurologie. "
        "Bitte nennen Sie die Fachrichtung, zum Beispiel: "
        '„Termin Innere Medizin im MVZ Nürnberg Süd".'
    )


def test_fachrichtung_mit_einem_standort_liefert_termine() -> None:
    ergebnis, terminsystem = chat("Ich brauche einen Termin in der Kardiologie")

    assert terminsystem.aufrufe == [("std-007", "Kardiologie", None, MAX_TERMINE)]
    assert ergebnis.termin_vorschlag == [slot("std-007", "Kardiologie", m) for m in range(5)]
    assert ergebnis.kategorie == "normal"
    assert ergebnis.quellen == STANDORTVERZEICHNIS
    assert "MVZ Schwabach" in ergebnis.antwort
    assert not any(zeichen.isdigit() for zeichen in ergebnis.antwort)


def test_fachrichtung_mit_einem_standort_ohne_freie_termine() -> None:
    ergebnis, _ = chat("Ich brauche einen Termin in der Kardiologie", StubTerminsystem(0))

    assert ergebnis.termin_vorschlag is None
    assert "keine freien Termine" in ergebnis.antwort
    assert "MVZ Schwabach" in ergebnis.antwort


def test_fachrichtung_mit_mehreren_standorten_nennt_standorte() -> None:
    ergebnis, terminsystem = chat("Kann ich einen Termin in der Neurologie vereinbaren?")

    assert_regelbasiert_ohne_aktion(ergebnis, terminsystem)
    assert ergebnis.antwort == (
        "Neurologie gibt es im Verbund an mehreren Standorten: MVZ Nürnberg Süd und "
        "MVZ Erlangen. Bitte nennen Sie den Standort, zum Beispiel: "
        '„Termin Neurologie im MVZ Nürnberg Süd".'
    )
    assert "MVZ Erlangen Süd" not in ergebnis.antwort


def test_notfall_hat_vorrang() -> None:
    ergebnis, terminsystem = chat("Ich brauche einen Termin, ich habe starke Brustschmerzen")

    assert ergebnis.kategorie == "notfall"
    assert terminsystem.aufrufe == []
