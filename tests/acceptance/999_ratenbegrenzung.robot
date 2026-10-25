*** Settings ***
Documentation       Spec 006 – Ratenbegrenzung des Chats.
...                 Läuft absichtlich als letzte Suite, weil sie das Limit für
...                 diese IP-Adresse ausschöpft. Danach wird eine Minute gewartet,
...                 damit nachfolgende Befehle (z. B. make eval) nicht blockiert werden.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Suite Teardown      Sleep    61s    Limit-Fenster ablaufen lassen
Test Tags           spec-006    fake-only


*** Test Cases ***
Mehr als 60 Nachrichten pro Minute werden begrenzt
    ${body}=    Create Dictionary    nachricht=Hallo
    ${codes}=    Create List
    FOR    ${i}    IN RANGE    70
        ${antwort}=    POST On Session    api    /api/chat    json=${body}    expected_status=any
        Append To List    ${codes}    ${antwort.status_code}
        IF    ${antwort.status_code} == 429
            Should Be Equal    ${antwort.json()}[detail]    Zu viele Anfragen. Bitte warten Sie einen Moment.
        END
    END
    List Should Contain Value    ${codes}    ${429}
