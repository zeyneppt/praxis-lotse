*** Settings ***
Documentation       Spec 007 – Evaluation läuft, schreibt Berichte und erfüllt die Schwellenwerte.
Library             Process
Library             OperatingSystem
Library             Collections
Test Tags           spec-007


*** Variables ***
${WURZEL}           ${CURDIR}/../..
${ERGEBNIS}         ${WURZEL}/reports/eval/ergebnis.json


*** Test Cases ***
Retrieval-Evaluation besteht die Schwellenwerte
    Remove File    ${ERGEBNIS}
    ${lauf}=    Run Process    make    eval    cwd=${WURZEL}    timeout=10 min    stderr=STDOUT
    Log    ${lauf.stdout}
    Should Be Equal As Integers    ${lauf.rc}    0
    File Should Exist    ${ERGEBNIS}
    File Should Exist    ${WURZEL}/reports/eval/ergebnis.md
    ${json}=    Get File    ${ERGEBNIS}
    ${e}=    Evaluate    json.loads($json)    modules=json
    Should Be Equal    ${e}[modus]    retrieval
    Should Be True    $e["bestanden"] is True
    Should Be True    $e["kennzahlen"]["retrieval_treffer_top3"] >= 0.85
    Should Be Equal As Numbers    ${e}[kennzahlen][notfall_erkennung]    1.0

Jede Frage aus fragen.yaml erscheint im Ergebnis
    ${json}=    Get File    ${ERGEBNIS}
    ${e}=    Evaluate    json.loads($json)    modules=json
    ${ids}=    Evaluate    [f["id"] for f in $e["fragen"]]
    FOR    ${id}    IN    w01    w21    n01    n04
        List Should Contain Value    ${ids}    ${id}
    END
