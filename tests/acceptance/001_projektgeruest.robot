*** Settings ***
Documentation       Spec 001 – Projektgerüst: Backend, Datenbank und Frontend laufen.
Resource            resources/api.resource
Library             Browser
Suite Setup         API Sitzung Öffnen
Test Tags           spec-001


*** Test Cases ***
Health-Endpunkt meldet Backend und Datenbank bereit
    ${antwort}=    GET Erwarte Status    /api/health    200
    Should Be Equal    ${antwort.json()}[status]    ok
    Should Be Equal    ${antwort.json()}[datenbank]    ok
    Should Contain Any    ${antwort.json()}[llm_provider]    fake    ollama    anthropic

Unbekannter Pfad liefert 404
    GET Erwarte Status    /api/gibt-es-nicht    404

Frontend zeigt die Überschrift Praxis-Lotse
    New Browser    chromium    headless=True
    New Page    ${UI_URL}
    Get Text    h1    ==    Praxis-Lotse
    [Teardown]    Close Browser
