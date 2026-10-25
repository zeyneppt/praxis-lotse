*** Settings ***
Documentation       Spec 004 – Chat-Assistent.
...                 Tests ohne Tag `llm` laufen mit LLM_PROVIDER=fake (CI).
...                 Tests mit Tag `llm` brauchen ein echtes Modell, z. B. LLM_PROVIDER=ollama (make acceptance-llm).
Resource            resources/api.resource
Suite Setup         API Sitzung Öffnen
Test Tags           spec-004


*** Test Cases ***
Antwort hat die Struktur aus dem Vertrag
    ${a}=    Chat Senden    Was darf ich vor einer Darmspiegelung essen?
    FOR    ${feld}    IN    sitzung_id    antwort    kategorie    quellen    aktion    ki_hinweis
        Dictionary Should Contain Key    ${a}    ${feld}
    END
    Should Be Equal    ${a}[kategorie]    normal
    Should Be Equal    ${a}[ki_hinweis]    ${KI_HINWEIS}
    Should Match Regexp    ${a}[sitzung_id]    ^[0-9a-f-]{36}$

Antwort stützt sich auf die richtige Quelle
    ${a}=    Chat Senden    Was darf ich vor einer Darmspiegelung essen?
    Quellen Enthalten Dokument    ${a}    darmspiegelung-vorbereitung.md

Quellen sind eindeutig
    ${a}=    Chat Senden    Wie bereite ich mich auf die Magenspiegelung vor?
    ${dokumente}=    Evaluate    [q["dokument"] for q in $a["quellen"]]
    List Should Not Contain Duplicates    ${dokumente}

Sitzung wird fortgeführt
    ${erste}=    Chat Senden    Hallo
    ${zweite}=    Chat Senden    Und was muss ich zum ersten Termin mitbringen?    ${erste}[sitzung_id]
    Should Be Equal    ${erste}[sitzung_id]    ${zweite}[sitzung_id]

Testmodus antwortet deterministisch
    [Tags]    fake-only
    ${a}=    Chat Senden    Wie lange vorher muss ich einen Termin absagen?
    Should Start With    ${a}[antwort]    [Testmodus] Gefunden in: Termine verschieben und absagen

Leere Nachricht wird abgelehnt
    ${body}=    Create Dictionary    nachricht=${EMPTY}
    POST Erwarte Status    /api/chat    ${body}    422

Zu lange Nachricht wird abgelehnt
    ${lang}=    Evaluate    "a" * 1001
    ${body}=    Create Dictionary    nachricht=${lang}
    POST Erwarte Status    /api/chat    ${body}    422

Standortfrage nutzt das Standortverzeichnis
    [Tags]    llm
    ${a}=    Chat Senden    Wo gibt es in Erlangen eine Gastroenterologie?
    Quellen Enthalten Dokument    ${a}    standorte.json
    Text Enthält Ohne Groß Klein    ${a}[antwort]    MVZ Erlangen

Wissensfrage wird aus dem Dokument beantwortet
    [Tags]    llm
    ${a}=    Chat Senden    Darf ich nach der Darmspiegelung selbst Auto fahren?
    Quellen Enthalten Dokument    ${a}    darmspiegelung-vorbereitung.md
    Text Enthält Ohne Groß Klein    ${a}[antwort]    24 Stunden

Antwort ist kurz
    [Tags]    llm
    ${a}=    Chat Senden    Was muss ich zum ersten Termin mitbringen?
    ${woerter}=    Evaluate    len($a["antwort"].split())
    Should Be True    ${woerter} <= 150

Unbekanntes wird nicht erfunden
    [Tags]    llm
    ${a}=    Chat Senden    Gibt es an einem Standort Akupunktur?
    Should Match Regexp    ${a}[antwort]    (?i)(nicht|keine).*(gefunden|informationen|angaben)|(telefon|anrufen)

Kontext der Sitzung wird genutzt
    [Tags]    llm
    ${erste}=    Chat Senden    Ich interessiere mich für den Standort in Schwabach.
    ${zweite}=    Chat Senden    Welche Fachrichtungen gibt es dort?    ${erste}[sitzung_id]
    Text Enthält Ohne Groß Klein    ${zweite}[antwort]    Kardiologie
