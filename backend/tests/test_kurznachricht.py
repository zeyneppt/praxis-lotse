import pytest

from app.chat import run_chat, strip_markdown
from app.leitplanken import texte
from app.leitplanken.kurznachricht import erkenne_kurznachricht
from app.llm.base import AssistantMessage, Message, ToolSpec
from tests.test_terminwunsch import ErfinderProvider, KeinLlm, StubTerminsystem, kasten

# --- (a) Kurze Nachrichten ohne Frageinhalt ----------------------------------


@pytest.mark.parametrize(
    ("nachricht", "erwartet"),
    [
        ("ja", "kurz"),
        ("Ok", "kurz"),
        ("nein.", "kurz"),
        ("Ja, bitte", "kurz"),
        ("Hallo", "kurz"),
        ("Hilfe!", "kurz"),
        ("Okay gut", "kurz"),
        ("Tschüss", "kurz"),
        ("?", None),
        ("danke", "danke"),
        ("Danke!", "danke"),
        ("Vielen Dank", "danke"),
        ("Dankeschön", "danke"),
        ("Was muss ich mitbringen?", None),
        ("Ja, das passt gut", None),
        ("Danke, und wann ist geöffnet?", None),
        # Frageinhalt: Wort mit „termin", Fachrichtung, Ort oder Standort (Review)
        ("Termin verschieben", None),
        ("Termin absagen", None),
        ("Termin Kardiologie", None),
        ("Termine Neurologie?", None),
        ("Neurologie Erlangen", None),
        ("Öffnungszeiten Fürth?", None),
        ("Kardiologie?", None),
        ("MVZ Lauf", None),
        ("Danke, Fürth", None),
        # Kurze Fragen mit Inhalt (Review-Runde 3)
        ("Öffnungszeiten?", None),
        ("Rezept bestellen", None),
        ("Parkplätze vorhanden?", None),
        ("Akupunktur?", None),
        ("Frage", None),
    ],
)
def test_kurznachricht_erkannt(nachricht: str, erwartet: str | None) -> None:
    assert erkenne_kurznachricht(nachricht) == erwartet


@pytest.mark.parametrize("nachricht", ["ja", "ok", "nein", "Ja bitte"])
def test_kurznachricht_ohne_llm(nachricht: str) -> None:
    ergebnis = run_chat(KeinLlm(), "system", [], nachricht, kasten(StubTerminsystem()))

    assert ergebnis.antwort == texte.KURZNACHRICHT
    assert ergebnis.antwort.startswith("Ich kann frühere Nachrichten nicht fortsetzen.")
    assert ergebnis.kategorie == "normal"
    assert ergebnis.quellen == []
    assert ergebnis.termin_vorschlag is None
    assert ergebnis.werkzeugaufrufe == 0


@pytest.mark.parametrize("nachricht", ["Hilfe!", "hilfe", "ja", "Hallo"])
def test_kurznachricht_nennt_112_und_116117(nachricht: str) -> None:
    # Entscheidung Mensch (Review Spec 010): Kurze Hilferufe dürfen nicht ohne 112 bleiben.
    ergebnis = run_chat(KeinLlm(), "system", [], nachricht, kasten(StubTerminsystem()))

    assert ergebnis.antwort.endswith(
        "Im Notfall rufen Sie die 112, den ärztlichen Bereitschaftsdienst erreichen Sie "
        "unter 116117."
    )


@pytest.mark.parametrize("nachricht", ["Notruf", "Notruf!", "Wie ist die Notrufnummer?"])
def test_notruf_loest_notfallantwort_aus(nachricht: str) -> None:
    ergebnis = run_chat(KeinLlm(), "system", [], nachricht, kasten(StubTerminsystem()))

    assert ergebnis.kategorie == "notfall"
    assert "112" in ergebnis.antwort


def test_danke_bekommt_kurze_freundliche_antwort() -> None:
    ergebnis = run_chat(KeinLlm(), "system", [], "Danke!", kasten(StubTerminsystem()))

    assert ergebnis.antwort == texte.KURZNACHRICHT_DANKE
    assert ergebnis.kategorie == "normal"


def test_kurzer_notfall_hat_vorrang() -> None:
    ergebnis = run_chat(KeinLlm(), "system", [], "Brustschmerzen", kasten(StubTerminsystem()))

    assert ergebnis.kategorie == "notfall"


def test_kurzer_terminwunsch_hat_vorrang() -> None:
    terminsystem = StubTerminsystem()

    ergebnis = run_chat(KeinLlm(), "system", [], "freie Termine", kasten(terminsystem))

    assert ergebnis.antwort.startswith("Gern suche ich freie Termine")


@pytest.mark.parametrize(
    "nachricht",
    ["Termin verschieben", "Termin Kardiologie", "Öffnungszeiten?", "Rezept bestellen"],
)
def test_kurze_nachricht_mit_frageinhalt_geht_an_llm(nachricht: str) -> None:
    ergebnis = run_chat(
        ErfinderProvider("Antwort aus der Wissensbasis."),
        "system",
        [],
        nachricht,
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == "Antwort aus der Wissensbasis."


def test_laengere_nachricht_geht_an_llm() -> None:
    ergebnis = run_chat(
        ErfinderProvider("Bitte bringen Sie die Versichertenkarte mit."),
        "system",
        [],
        "Ja, was soll ich mitbringen?",
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == "Bitte bringen Sie die Versichertenkarte mit."


# --- (b) Markdown in LLM-Antworten -------------------------------------------


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("Das ist **wichtig**.", "Das ist wichtig."),
        ("Das ist __wichtig__.", "Das ist wichtig."),
        ("**Fürth:** 07:30 und **Stein:** 08:00", "Fürth: 07:30 und Stein: 08:00"),
        ("Siehe [Webseite](https://example.org/a_b).", "Siehe Webseite."),
        ("[Anrufen](tel:+499110000004)", "Anrufen"),
        ("# Öffnungszeiten\nMo 8–12", "Öffnungszeiten\nMo 8–12"),
        ("Text\n### Hinweis\nMehr", "Text\nHinweis\nMehr"),
        ("- Versichertenkarte\n- Überweisung", "- Versichertenkarte\n- Überweisung"),
        ("Rufen Sie +49 911 0000004 an.", "Rufen Sie +49 911 0000004 an."),
        ("Nr. #3 bleibt", "Nr. #3 bleibt"),
        ("snake_case und 2*3*4", "snake_case und 2*3*4"),
        ("Datei __init__.py", "Datei __init__.py"),
        ("[Info](https://example.org/a_(b))", "Info"),
    ],
)
def test_strip_markdown(roh: str, erwartet: str) -> None:
    assert strip_markdown(roh) == erwartet


class MarkdownProvider:
    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        allow_tools: bool = True,
    ) -> AssistantMessage:
        if len(messages) == 1:
            return ErfinderProvider("").complete(system, messages, tools, allow_tools)
        return AssistantMessage(
            "## Antwort\n**MVZ Fürth Zentrum**: [Testallee 3](https://example.org)\n"
            "**Quellen:** standorte.json"
        )

    def check_available(self) -> None:
        return None


def test_llm_antwort_ohne_markdown() -> None:
    ergebnis = run_chat(
        MarkdownProvider(),
        "system",
        [],
        "Wo ist der Standort in Fürth?",
        kasten(StubTerminsystem()),
    )

    assert ergebnis.antwort == "Antwort\nMVZ Fürth Zentrum: Testallee 3"
    assert [q.dokument for q in ergebnis.quellen] == ["standorte.json"]
