*** Settings ***
Documentation       Gemeinsame Schlüsselwörter für die API-Abnahmetests von Praxis-Lotse.
Library             RequestsLibrary
Library             Collections
Library             String


*** Variables ***
${API_URL}          http://localhost:8000
${UI_URL}           http://localhost:5173
${KI_HINWEIS}       Sie sprechen mit einem KI-Assistenten. Er ersetzt keine ärztliche Beratung.


*** Keywords ***
API Sitzung Öffnen
    Create Session    api    ${API_URL}    timeout=60

GET Erwarte Status
    [Arguments]    ${pfad}    ${status}=200    &{params}
    ${antwort}=    GET On Session    api    ${pfad}    params=${params}    expected_status=${status}
    RETURN    ${antwort}

POST Erwarte Status
    [Arguments]    ${pfad}    ${body}    ${status}=200
    ${antwort}=    POST On Session    api    ${pfad}    json=${body}    expected_status=${status}
    RETURN    ${antwort}

Chat Senden
    [Documentation]    Sendet eine Nachricht an den Chat und gibt das JSON der Antwort zurück.
    [Arguments]    ${nachricht}    ${sitzung_id}=${NONE}
    IF    $sitzung_id is None
        ${body}=    Create Dictionary    nachricht=${nachricht}
    ELSE
        ${body}=    Create Dictionary    nachricht=${nachricht}    sitzung_id=${sitzung_id}
    END
    ${antwort}=    POST Erwarte Status    /api/chat    ${body}    200
    RETURN    ${antwort.json()}

Quellen Enthalten Dokument
    [Arguments]    ${chat_antwort}    ${dokument}
    ${dokumente}=    Evaluate    [q["dokument"] for q in $chat_antwort["quellen"]]
    List Should Contain Value    ${dokumente}    ${dokument}

Text Enthält Ohne Groß Klein
    [Arguments]    ${text}    ${erwartet}
    ${klein}=    Convert To Lower Case    ${text}
    ${erwartet_klein}=    Convert To Lower Case    ${erwartet}
    Should Contain    ${klein}    ${erwartet_klein}

Alle Standort IDs
    [Arguments]    ${antwort}
    ${ids}=    Evaluate    [s["id"] for s in $antwort.json()]
    RETURN    ${ids}
