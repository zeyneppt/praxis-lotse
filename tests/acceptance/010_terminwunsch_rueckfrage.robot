*** Settings ***
Documentation       Spec 010 – Unvollständiger Terminwunsch wird regelbasiert beantwortet.
...                 Antworten des Fake-Providers beginnen mit [Testmodus]; fehlt das,
...                 hat der Server ohne LLM geantwortet.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-010


*** Test Cases ***
Terminwunsch ohne Angaben führt zur Rückfrage
    ${a}=    Chat Senden    Welche freien Termine gibt es bei Ihnen?
    Regelbasiert Ohne Aktion    ${a}
    FOR    ${fach}    IN    Gastroenterologie    Kardiologie    Neurologie    Orthopädie
        Should Contain    ${a}[antwort]    ${fach}
    END
    Should Contain    ${a}[antwort]    Termin Gastroenterologie in Fürth

Nur Ort genannt nennt die Fachrichtungen dort
    ${a}=    Chat Senden    Ich möchte einen Termin in Fürth
    Regelbasiert Ohne Aktion    ${a}
    Should Contain    ${a}[antwort]    Gastroenterologie
    Should Contain    ${a}[antwort]    Endoskopie
    Should Not Contain    ${a}[antwort]    Kardiologie

Nur Fachrichtung mit genau einem Standort liefert Termine
    ${a}=    Chat Senden    Ich brauche einen Termin in der Kardiologie
    Should Be Equal    ${a}[kategorie]    normal
    Should Not Be Equal    ${a}[aktion]    ${NONE}
    Should Be Equal    ${a}[aktion][typ]    termin_vorschlag
    ${slots}=    Set Variable    ${a}[aktion][slots]
    Should Not Be Empty    ${slots}
    FOR    ${slot}    IN    @{slots}
        Should Be Equal    ${slot}[standort_id]    std-007
        Should Be Equal    ${slot}[fachrichtung]    Kardiologie
    END
    Should Contain    ${a}[antwort]    MVZ Schwabach

Nur Fachrichtung mit mehreren Standorten nennt die Standorte
    ${a}=    Chat Senden    Kann ich einen Termin in der Neurologie vereinbaren?
    Regelbasiert Ohne Aktion    ${a}
    Should Contain    ${a}[antwort]    MVZ Nürnberg Süd
    Should Contain    ${a}[antwort]    MVZ Erlangen
    Should Not Contain    ${a}[antwort]    MVZ Erlangen Süd

Termin absagen bleibt bei der Wissensbasis
    ${a}=    Chat Senden    Ich möchte meinen Termin absagen
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Start With    ${a}[antwort]    [Testmodus]


*** Keywords ***
Regelbasiert Ohne Aktion
    [Arguments]    ${a}
    Should Be Equal    ${a}[kategorie]    normal
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Not Start With    ${a}[antwort]    [Testmodus]
    Should Not Match Regexp    ${a}[antwort]    \\b\\d{1,2}[:.]\\d{2}\\b
    Quellen Enthalten Dokument    ${a}    standorte.json
