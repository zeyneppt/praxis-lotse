*** Settings ***
Documentation       Spec 002 – Standortsuche nach Fachrichtung und Ort.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-002


*** Test Cases ***
Ohne Filter werden alle 12 Standorte sortiert geliefert
    ${antwort}=    GET Erwarte Status    /api/standorte
    ${ids}=    Alle Standort IDs    ${antwort}
    Length Should Be    ${ids}    12
    Should Be Equal    ${ids}[0]    std-001
    Should Be Equal    ${ids}[-1]    std-012

Standort hat alle Felder aus dem Vertrag
    ${antwort}=    GET Erwarte Status    /api/standorte/std-004
    ${s}=    Set Variable    ${antwort.json()}
    Should Be Equal    ${s}[name]    MVZ Fürth Zentrum
    Should Be Equal    ${s}[ort]    Fürth
    Should Be Equal    ${s}[plz]    90762
    Should Be True    $s["barrierefrei"] is True
    Should Be Equal    ${s}[oeffnungszeiten][fr]    07:30-12:00
    FOR    ${feld}    IN    id    name    ort    stadtteil    adresse    plz    telefon    fachrichtungen    oeffnungszeiten    barrierefrei
        Dictionary Should Contain Key    ${s}    ${feld}
    END

Unbekannter Standort liefert 404
    ${antwort}=    GET Erwarte Status    /api/standorte/std-999    404
    Should Be Equal    ${antwort.json()}[detail]    Standort nicht gefunden

Teilwort der Fachrichtung findet alle Gastroenterologie-Standorte
    ${antwort}=    GET Erwarte Status    /api/standorte    fachrichtung=gastro
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-001    std-004    std-009
    Lists Should Be Equal    ${ids}    ${erwartet}

Groß- und Kleinschreibung spielt keine Rolle
    ${antwort}=    GET Erwarte Status    /api/standorte    fachrichtung=NEUROLOGIE
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-003    std-009
    Lists Should Be Equal    ${ids}    ${erwartet}

Umschriebene Umlaute werden erkannt
    ${antwort}=    GET Erwarte Status    /api/standorte    fachrichtung=gynaekologie
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-002    std-006    std-010
    Lists Should Be Equal    ${ids}    ${erwartet}

Filter nach Ort
    ${antwort}=    GET Erwarte Status    /api/standorte    ort=nürnberg
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-001    std-002    std-003    std-005
    Lists Should Be Equal    ${ids}    ${erwartet}

Teilwort im Ort
    ${antwort}=    GET Erwarte Status    /api/standorte    ort=lauf
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-012
    Lists Should Be Equal    ${ids}    ${erwartet}

Fachrichtung und Ort kombiniert
    ${antwort}=    GET Erwarte Status    /api/standorte    fachrichtung=Gastroenterologie    ort=Erlangen
    ${ids}=    Alle Standort IDs    ${antwort}
    ${erwartet}=    Create List    std-009
    Lists Should Be Equal    ${ids}    ${erwartet}

Unbekannte Fachrichtung liefert leere Liste statt Fehler
    ${antwort}=    GET Erwarte Status    /api/standorte    fachrichtung=Zahnmedizin
    Should Be Empty    ${antwort.json()}

Fachrichtungen sind eindeutig und alphabetisch
    ${antwort}=    GET Erwarte Status    /api/fachrichtungen
    ${erwartet}=    Create List    Allgemeinmedizin    Endoskopie    Gastroenterologie    Gynäkologie
    ...    Innere Medizin    Kardiologie    Neurologie    Orthopädie
    Lists Should Be Equal    ${antwort.json()}    ${erwartet}
