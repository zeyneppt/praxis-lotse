*** Settings ***
Documentation       Spec 009 – Terminwunsch wird regelbasiert vor dem LLM erkannt.
...                 Läuft mit LLM_PROVIDER=fake deterministisch: Der Fake-Provider
...                 erzeugt nie eine aktion, eine aktion kann also nur vom Server kommen.
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-009


*** Test Cases ***
Eindeutiger Terminwunsch liefert echte Termine
    ${a}=    Chat Senden    Ich hätte gern einen Termin in der Gastroenterologie in Fürth.
    Termine Für Standort    ${a}    std-004    Gastroenterologie
    Should Contain    ${a}[antwort]    MVZ Fürth Zentrum
    Quellen Enthalten Dokument    ${a}    standorte.json
    Should Not Match Regexp    ${a}[antwort]    \\b\\d{1,2}[:.]\\d{2}\\b

Schreibweise ohne Umlaute und ohne Satz
    ${a}=    Chat Senden    termin kardiologie schwabach
    Termine Für Standort    ${a}    std-007    Kardiologie

Wortform der Fachrichtung wird erkannt
    ${a}=    Chat Senden    Ich suche einen Termin beim Neurologen in Erlangen
    Termine Für Standort    ${a}    std-009    Neurologie

Mehrteiliger Ort wird am ersten Wort erkannt
    ${a}=    Chat Senden    Gibt es Termine für Innere Medizin in Lauf?
    Termine Für Standort    ${a}    std-012    Innere Medizin

Mehrere passende Standorte werden zur Auswahl genannt
    ${a}=    Chat Senden    Ich brauche einen Termin für Innere Medizin in Nürnberg
    Should Be Equal    ${a}[kategorie]    normal
    Should Be Equal    ${a}[aktion]    ${NONE}
    FOR    ${name}    IN    MVZ Nürnberg Mitte    MVZ Nürnberg Süd    MVZ Nürnberg West
        Should Contain    ${a}[antwort]    ${name}
    END
    Should Not Contain    ${a}[antwort]    MVZ Nürnberg Nord

Fachrichtung gibt es am Ort nicht
    ${a}=    Chat Senden    Ich möchte einen Termin in der Kardiologie in Fürth
    Should Be Equal    ${a}[kategorie]    normal
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Contain    ${a}[antwort]    MVZ Schwabach

Wissensfrage mit dem Wort Termin bleibt beim bisherigen Ablauf
    ${a}=    Chat Senden    Was muss ich zum ersten Termin mitbringen?
    Should Be Equal    ${a}[aktion]    ${NONE}
    Should Start With    ${a}[antwort]    [Testmodus]

Notfall hat Vorrang vor dem Terminwunsch
    ${a}=    Chat Senden    Ich brauche einen Termin in der Kardiologie in Schwabach, ich habe starke Brustschmerzen
    Should Be Equal    ${a}[kategorie]    notfall
    Should Be Equal    ${a}[aktion]    ${NONE}


*** Keywords ***
Termine Für Standort
    [Arguments]    ${a}    ${standort_id}    ${fachrichtung}
    Should Be Equal    ${a}[kategorie]    normal
    Should Not Be Equal    ${a}[aktion]    ${NONE}
    Should Be Equal    ${a}[aktion][typ]    termin_vorschlag
    ${slots}=    Set Variable    ${a}[aktion][slots]
    Should Not Be Empty    ${slots}
    ${anzahl}=    Get Length    ${slots}
    Should Be True    ${anzahl} <= 5
    FOR    ${slot}    IN    @{slots}
        Should Be Equal    ${slot}[standort_id]    ${standort_id}
        Should Be Equal    ${slot}[fachrichtung]    ${fachrichtung}
    END
    # Jeder vorgeschlagene Termin ist im Terminsystem wirklich frei.
    ${freie}=    GET Erwarte Status    /api/termine/freie    200
    ...    standort_id=${standort_id}    fachrichtung=${fachrichtung}    limit=50
    ${ids}=    Evaluate    [s["slot_id"] for s in $freie.json()]
    FOR    ${slot}    IN    @{slots}
        List Should Contain Value    ${ids}    ${slot}[slot_id]
    END
