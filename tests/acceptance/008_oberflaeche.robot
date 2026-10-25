*** Settings ***
Documentation       Spec 008 – Chat-Oberfläche im Browser.
Resource            resources/api.resource
Library             Browser
Suite Setup         New Browser    chromium    headless=True
Suite Teardown      Close Browser
Test Setup          New Page    ${UI_URL}
Test Teardown       Close Page
Test Tags           spec-008


*** Test Cases ***
KI-Hinweis ist sofort sichtbar
    Get Text    [data-testid="ki-hinweis"]    contains    KI-Assistenten

Frage stellen und Antwort mit Quellen erhalten
    Frage Stellen    Was darf ich vor einer Darmspiegelung essen?
    Get Element Count    [data-testid="nachricht-person"]    ==    1
    Wait For Elements State    [data-testid="nachricht-assistent"] >> nth=0    visible    timeout=60s
    Get Text    [data-testid="nachricht-assistent"] >> nth=0 >> [data-testid="quellen"]    contains    Darmspiegelung

Enter sendet die Nachricht
    Fill Text    [data-testid="chat-eingabe"]    Was muss ich zum ersten Termin mitbringen?
    Keyboard Key    press    Enter
    Wait For Elements State    [data-testid="nachricht-assistent"] >> nth=0    visible    timeout=60s
    Get Text    [data-testid="chat-eingabe"]    ==    ${EMPTY}

Notfall wird hervorgehoben und Nummer ist anrufbar
    Frage Stellen    Ich habe starke Brustschmerzen und bekomme schlecht Luft
    ${notfall}=    Set Variable    [data-testid="nachricht-assistent"][data-kategorie="notfall"]
    Wait For Elements State    ${notfall}    visible    timeout=30s
    Get Text    ${notfall}    contains    112
    Get Attribute    ${notfall} >> a[href^="tel:"] >> nth=0    href    ==    tel:112

Bedienelemente sind beschriftet
    ${label}=    Get Attribute    [data-testid="chat-eingabe"]    aria-label
    Should Not Be Empty    ${label}
    ${knopf}=    Get Text    [data-testid="chat-senden"]
    Should Not Be Empty    ${knopf}

Auf dem Smartphone gibt es kein horizontales Scrollen
    Set Viewport Size    375    740
    Frage Stellen    Was muss ich zum ersten Termin mitbringen?
    Wait For Elements State    [data-testid="nachricht-assistent"] >> nth=0    visible    timeout=60s
    ${breite}=    Evaluate JavaScript    ${NONE}    document.documentElement.scrollWidth
    Should Be True    ${breite} <= 375

Terminanfrage über das Formular
    [Tags]    llm
    Frage Stellen    Ich hätte gern einen Termin in der Gastroenterologie in Fürth.
    Wait For Elements State    [data-testid="termin-slot"] >> nth=0    visible    timeout=60s
    Click    [data-testid="termin-slot"] >> nth=0
    Fill Text    [data-testid="termin-name"]    Erika Mustermann
    Fill Text    [data-testid="termin-geburtsdatum"]    1970-05-14
    Fill Text    [data-testid="termin-telefon"]    +49 170 0000000
    Check Checkbox    [data-testid="termin-einwilligung"]
    Click    [data-testid="termin-absenden"]
    Wait For Elements State    [data-testid="termin-bestaetigung"]    visible    timeout=30s
    Get Text    [data-testid="termin-bestaetigung"]    contains    Fürth


*** Keywords ***
Frage Stellen
    [Arguments]    ${frage}
    Fill Text    [data-testid="chat-eingabe"]    ${frage}
    Click    [data-testid="chat-senden"]
