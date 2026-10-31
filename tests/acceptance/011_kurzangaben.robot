*** Settings ***
Documentation       Spec 011 – Kurzangaben ohne das Wort „Termin" werden wie ein Terminwunsch behandelt.
...                 Antworten des Fake-Providers beginnen mit [Testmodus]; fehlt das,
...                 hat der Server ohne LLM geantwortet.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-011


*** Test Cases ***
Fachrichtung und Ort liefern Termine
    ${a}=    Chat Senden    Gastroenterologie in Fürth
    Termine Für Standort    ${a}    std-004    Gastroenterologie

Fachrichtung, die es am Ort nicht gibt
    ${a}=    Chat Senden    Kardiologie Fürth
    Should Be Equal    ${a}[kategorie]    normal
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Not Start With    ${a}[antwort]    [Testmodus]
    Should Contain    ${a}[antwort]    MVZ Schwabach

Nur Fachrichtung mit mehreren Standorten
    ${a}=    Chat Senden    Neurologie bitte
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Not Start With    ${a}[antwort]    [Testmodus]
    Should Contain    ${a}[antwort]    MVZ Nürnberg Süd
    Should Contain    ${a}[antwort]    MVZ Erlangen

Standortname mit Füllwörtern
    ${a}=    Chat Senden    Ja, Kardiologie im MVZ Schwabach.
    Termine Für Standort    ${a}    std-007    Kardiologie

Weitere Wörter führen nicht zur Kurzangabe
    ${a}=    Chat Senden    Öffnungszeiten der Kardiologie in Schwabach?
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Start With    ${a}[antwort]    [Testmodus]


*** Keywords ***
Termine Für Standort
    [Arguments]    ${a}    ${standort_id}    ${fachrichtung}
    Should Be Equal    ${a}[kategorie]    normal
    Should Not Be Equal    ${a}[aktion]    ${NONE}
    Should Be Equal    ${a}[aktion][typ]    termin_vorschlag
    ${slots}=    Set Variable    ${a}[aktion][slots]
    Should Not Be Empty    ${slots}
    FOR    ${slot}    IN    @{slots}
        Should Be Equal    ${slot}[standort_id]    ${standort_id}
        Should Be Equal    ${slot}[fachrichtung]    ${fachrichtung}
    END
    Quellen Enthalten Dokument    ${a}    standorte.json
