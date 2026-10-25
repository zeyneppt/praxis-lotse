*** Settings ***
Documentation       Spec 003 – Wissensbasis: Ingest und semantische Suche.
...                 Voraussetzung: `make ingest` wurde ausgeführt.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-003


*** Test Cases ***
Alle acht Dokumente sind indexiert
    ${antwort}=    GET Erwarte Status    /api/wissen/dokumente
    ${dokumente}=    Evaluate    [d["dokument"] for d in $antwort.json()]
    ${erwartet}=    Create List    blutabnahme.md    darmspiegelung-vorbereitung.md    erster-besuch.md
    ...    gynaekologie-vorsorge.md    magenspiegelung-vorbereitung.md
    ...    notfall-und-bereitschaftsdienst.md    rezepte-und-ueberweisungen.md    termin-absagen.md
    Lists Should Be Equal    ${dokumente}    ${erwartet}

Abschnitte entsprechen den Zwischenüberschriften
    ${antwort}=    GET Erwarte Status    /api/wissen/dokumente
    ${darm}=    Evaluate    [d for d in $antwort.json() if d["dokument"] == "darmspiegelung-vorbereitung.md"][0]
    Should Be Equal As Integers    ${darm}[abschnitte]    5
    Should Be Equal    ${darm}[titel]    Vorbereitung auf die Darmspiegelung (Koloskopie)

Suche findet das passende Dokument mit anderen Worten
    [Documentation]    „Koloskopie“ und „essen“ statt „Darmspiegelung“ und „Ernährung“.
    ${body}=    Create Dictionary    frage=Was darf ich vor der Koloskopie essen?
    ${antwort}=    POST Erwarte Status    /api/wissen/suche    ${body}
    ${treffer}=    Set Variable    ${antwort.json()}[treffer]
    Length Should Be    ${treffer}    3
    Should Be Equal    ${treffer}[0][dokument]    darmspiegelung-vorbereitung.md

Treffer haben alle Felder und absteigende Scores
    ${body}=    Create Dictionary    frage=Wie lange vorher muss ich einen Termin absagen?    k=${5}
    ${antwort}=    POST Erwarte Status    /api/wissen/suche    ${body}
    ${treffer}=    Set Variable    ${antwort.json()}[treffer]
    Length Should Be    ${treffer}    5
    Should Be Equal    ${treffer}[0][dokument]    termin-absagen.md
    FOR    ${feld}    IN    dokument    titel    abschnitt    text    score
        Dictionary Should Contain Key    ${treffer}[0]    ${feld}
    END
    ${scores}=    Evaluate    [t["score"] for t in $treffer]
    ${sortiert}=    Evaluate    sorted($scores, reverse=True)
    Lists Should Be Equal    ${scores}    ${sortiert}

Höchstens zwei Treffer pro Dokument
    ${body}=    Create Dictionary    frage=Darmspiegelung Vorbereitung Abführmittel Ernährung Sedierung    k=${6}
    ${antwort}=    POST Erwarte Status    /api/wissen/suche    ${body}
    ${anzahl}=    Evaluate    max(collections.Counter(t["dokument"] for t in $antwort.json()["treffer"]).values())
    ...    modules=collections
    Should Be True    ${anzahl} <= 2

Hinweiskasten am Dokumentanfang wird nicht indexiert
    ${body}=    Create Dictionary    frage=Fiktives Beispieldokument für eine Demo    k=${10}
    ${antwort}=    POST Erwarte Status    /api/wissen/suche    ${body}
    ${treffer}=    Set Variable    ${antwort.json()}[treffer]
    FOR    ${t}    IN    @{treffer}
        Should Not Contain    ${t}[text]    Fiktives Beispieldokument
    END

Leere Frage wird abgelehnt
    ${body}=    Create Dictionary    frage=${EMPTY}
    POST Erwarte Status    /api/wissen/suche    ${body}    422

Zu langes k wird abgelehnt
    ${body}=    Create Dictionary    frage=Test    k=${11}
    POST Erwarte Status    /api/wissen/suche    ${body}    422

Zu lange Frage wird abgelehnt
    ${lang}=    Evaluate    "a" * 501
    ${body}=    Create Dictionary    frage=${lang}
    POST Erwarte Status    /api/wissen/suche    ${body}    422
