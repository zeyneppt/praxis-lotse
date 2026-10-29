*** Settings ***
Documentation       Spec 009 – Kompletter Terminablauf im Browser, ohne echtes LLM.
...                 Dasselbe Szenario wie der llm-Test in Spec 008, jetzt deterministisch.
Resource            resources/api.resource
Library             Browser
Suite Setup         New Browser    chromium    headless=True
Suite Teardown      Close Browser
Test Setup          New Page    ${UI_URL}
Test Teardown       Close Page
Test Tags           spec-009


*** Test Cases ***
Terminwunsch im Chat bis zur Bestätigung
    Fill Text    [data-testid="chat-eingabe"]    Ich hätte gern einen Termin in der Gastroenterologie in Fürth.
    Click    [data-testid="chat-senden"]
    Wait For Elements State    [data-testid="termin-slot"] >> nth=0    visible    timeout=30s
    Click    [data-testid="termin-slot"] >> nth=0
    Fill Text    [data-testid="termin-name"]    Erika Mustermann
    Fill Text    [data-testid="termin-geburtsdatum"]    1970-05-14
    Fill Text    [data-testid="termin-telefon"]    +49 170 0000000
    Check Checkbox    [data-testid="termin-einwilligung"]
    Click    [data-testid="termin-absenden"]
    Wait For Elements State    [data-testid="termin-bestaetigung"]    visible    timeout=30s
    Get Text    [data-testid="termin-bestaetigung"]    contains    Fürth
