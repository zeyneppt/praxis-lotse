*** Settings ***
Documentation       Spec 005 – Terminanfrage über das simulierte Terminsystem.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-005


*** Test Cases ***
Freie Termine eines Standorts werden sortiert geliefert
    ${antwort}=    GET Erwarte Status    /api/termine/freie    200    standort_id=std-004    fachrichtung=gastroenterologie
    ${slots}=    Set Variable    ${antwort.json()}
    Should Not Be Empty    ${slots}
    ${anzahl}=    Get Length    ${slots}
    Should Be True    ${anzahl} <= 10
    FOR    ${slot}    IN    @{slots}
        Should Be Equal    ${slot}[standort_id]    std-004
        Should Be Equal    ${slot}[standort_name]    MVZ Fürth Zentrum
        Should Be Equal    ${slot}[fachrichtung]    Gastroenterologie
        Should Start With    ${slot}[slot_id]    std-004|Gastroenterologie|
    END
    ${beginne}=    Evaluate    [s["beginn"] for s in $slots]
    ${sortiert}=    Evaluate    sorted($beginne)
    Lists Should Be Equal    ${beginne}    ${sortiert}

Termine liegen an Werktagen innerhalb der Öffnungszeiten
    [Documentation]    std-004 ist Mo–Do 07:30–15:00 und Fr 07:30–12:00 geöffnet.
    ${antwort}=    GET Erwarte Status    /api/termine/freie    200    standort_id=std-004    fachrichtung=Endoskopie    limit=50
    FOR    ${slot}    IN    @{antwort.json()}
        ${dt}=    Evaluate    datetime.datetime.fromisoformat($slot["beginn"])    modules=datetime
        Should Be True    $dt.weekday() < 5
        Should Be True    $dt.minute in (0, 30)
        ${minuten}=    Evaluate    $dt.hour * 60 + $dt.minute
        Should Be True    ${minuten} >= 450
        IF    $dt.weekday() == 4
            Should Be True    ${minuten} <= 690
        ELSE
            Should Be True    ${minuten} <= 870
        END
    END

Limit wird beachtet
    ${antwort}=    GET Erwarte Status    /api/termine/freie    200    standort_id=std-001    fachrichtung=Innere Medizin    limit=3
    Length Should Be    ${antwort.json()}    3

Unbekannter Standort liefert 404
    GET Erwarte Status    /api/termine/freie    404    standort_id=std-999    fachrichtung=Gastroenterologie

Fachrichtung, die der Standort nicht hat, liefert 422
    GET Erwarte Status    /api/termine/freie    422    standort_id=std-004    fachrichtung=Neurologie

Terminanfrage wird angelegt und enthält keine personenbezogenen Daten
    ${slot}=    Ersten Freien Termin Holen    std-009    Neurologie
    ${body}=    Gültige Anfrage    ${slot}[slot_id]
    ${antwort}=    POST Erwarte Status    /api/termine/anfragen    ${body}    201
    ${a}=    Set Variable    ${antwort.json()}
    Should Be Equal    ${a}[status]    angefragt
    Should Be Equal    ${a}[slot][slot_id]    ${slot}[slot_id]
    Should Match Regexp    ${a}[anfrage_id]    ^[0-9a-f-]{36}$
    FOR    ${feld}    IN    name    geburtsdatum    telefon
        Dictionary Should Not Contain Key    ${a}    ${feld}
    END
    Should Not Contain    ${antwort.text}    Mustermann
    ${abruf}=    GET Erwarte Status    /api/termine/anfragen/${a}[anfrage_id]    200
    Should Be Equal    ${abruf.json()}[slot][slot_id]    ${slot}[slot_id]
    Should Not Contain    ${abruf.text}    Mustermann

Angefragter Termin ist nicht mehr frei und kann nicht doppelt angefragt werden
    ${slot}=    Ersten Freien Termin Holen    std-002    Gynäkologie
    ${body}=    Gültige Anfrage    ${slot}[slot_id]
    POST Erwarte Status    /api/termine/anfragen    ${body}    201
    ${antwort}=    POST Erwarte Status    /api/termine/anfragen    ${body}    409
    Should Be Equal    ${antwort.json()}[detail]    Termin nicht mehr verfügbar
    ${freie}=    GET Erwarte Status    /api/termine/freie    200    standort_id=std-002    fachrichtung=Gynäkologie    limit=50
    ${ids}=    Evaluate    [s["slot_id"] for s in $freie.json()]
    List Should Not Contain Value    ${ids}    ${slot}[slot_id]

Ohne Einwilligung keine Anfrage
    ${slot}=    Ersten Freien Termin Holen    std-007    Kardiologie
    ${body}=    Gültige Anfrage    ${slot}[slot_id]
    Set To Dictionary    ${body}    einwilligung_datenschutz=${False}
    POST Erwarte Status    /api/termine/anfragen    ${body}    422

Ungültige Telefonnummer wird abgelehnt
    ${slot}=    Ersten Freien Termin Holen    std-007    Kardiologie
    ${body}=    Gültige Anfrage    ${slot}[slot_id]
    Set To Dictionary    ${body}    telefon=bitte anrufen
    POST Erwarte Status    /api/termine/anfragen    ${body}    422

Geburtsdatum in der Zukunft wird abgelehnt
    ${slot}=    Ersten Freien Termin Holen    std-007    Kardiologie
    ${body}=    Gültige Anfrage    ${slot}[slot_id]
    Set To Dictionary    ${body}    geburtsdatum=2099-01-01
    POST Erwarte Status    /api/termine/anfragen    ${body}    422

Erfundene Slot-ID wird abgelehnt
    ${body}=    Gültige Anfrage    std-004|Gastroenterologie|2020-01-06T09:00:00+01:00
    POST Erwarte Status    /api/termine/anfragen    ${body}    409

Unbekannte Anfrage liefert 404
    GET Erwarte Status    /api/termine/anfragen/00000000-0000-0000-0000-000000000000    404

Chat schlägt freie Termine vor
    [Tags]    llm
    ${a}=    Chat Senden    Ich hätte gern einen Termin in der Gastroenterologie in Fürth.
    Should Be Equal    ${a}[aktion][typ]    termin_vorschlag
    ${slots}=    Set Variable    ${a}[aktion][slots]
    Should Not Be Empty    ${slots}
    ${anzahl}=    Get Length    ${slots}
    Should Be True    ${anzahl} <= 5
    Should Be Equal    ${slots}[0][standort_id]    std-004


*** Keywords ***
Ersten Freien Termin Holen
    [Arguments]    ${standort_id}    ${fachrichtung}
    ${antwort}=    GET Erwarte Status    /api/termine/freie    200    standort_id=${standort_id}    fachrichtung=${fachrichtung}    limit=1
    Should Not Be Empty    ${antwort.json()}
    RETURN    ${antwort.json()}[0]

Gültige Anfrage
    [Arguments]    ${slot_id}
    ${body}=    Create Dictionary    slot_id=${slot_id}    name=Erika Mustermann    geburtsdatum=1970-05-14
    ...    telefon=+49 170 0000000    einwilligung_datenschutz=${True}
    RETURN    ${body}
