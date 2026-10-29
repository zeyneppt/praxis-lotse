"""Feste Texte der Leitplanken. Sie stehen hier und nicht im LLM-Prompt."""

NOTFALL_DOKUMENT = "notfall-und-bereitschaftsdienst.md"
NOTFALL_TITEL = "Notfälle und Bereitschaftsdienst"

NOTFALL_KOERPERLICH = (
    "Das klingt nach einem Notfall. Bitte rufen Sie sofort den Notruf 112 an. "
    "Warten Sie nicht auf einen Praxistermin und bleiben Sie, wenn möglich, bei der "
    "betroffenen Person, bis Hilfe eintrifft."
)

NOTFALL_SEELISCH = (
    "Es tut mir leid, dass es Ihnen gerade so schlecht geht. Sie sind nicht allein, und "
    "es gibt Menschen, die Ihnen jetzt zuhören. Die TelefonSeelsorge ist rund um die Uhr "
    "kostenlos und anonym erreichbar: 0800 111 0 111 oder 0800 111 0 222. "
    "Wenn Sie sich in akuter Gefahr befinden oder Ihnen etwas zustoßen könnte, rufen Sie "
    "bitte sofort die 112 an."
)

# Kennung im Systemprompt; taucht sie in einer Antwort auf, wurde der Prompt ausgegeben.
KANARIE = "PL-KANARIE-7731"

STANDARDANTWORT = (
    "Dabei kann ich Ihnen leider nicht helfen. Ich beantworte gern organisatorische Fragen "
    "zu Standorten, Terminen und Untersuchungen."
)

# Terminwunsch ohne LLM (Spec 009). Keine Uhrzeiten im Text: Die Termine zeigt die Oberfläche.
TERMINWUNSCH_TERMINE = (
    "Hier sind freie Termine für {fachrichtung} im {standort}. "
    "Wählen Sie einen Termin aus, um eine Terminanfrage zu stellen."
)
TERMINWUNSCH_KEINE_TERMINE = (
    "Im {standort} gibt es für {fachrichtung} derzeit keine freien Termine. "
    "Bitte rufen Sie den Standort an: {telefon}."
)
TERMINWUNSCH_MEHRERE = (
    "{fachrichtung} bieten in {ort} mehrere Standorte an: {standorte}. "
    "Bitte nennen Sie den Standort, an dem Sie einen Termin möchten."
)
TERMINWUNSCH_NICHT_AM_ORT = (
    "In {ort} bietet kein Standort des Verbunds {fachrichtung} an. "
    "{fachrichtung} gibt es im Verbund hier: {standorte}."
)

# Ersetzt eine Modellantwort mit Uhrzeit, wenn das Terminsystem keine Termine geliefert hat.
TERMIN_NUR_AUS_TERMINSYSTEM = (
    "Freie Termine kann ich Ihnen nur direkt aus dem Terminsystem zeigen. Bitte nennen Sie "
    'Fachrichtung und Ort, zum Beispiel: „Termin in der Gastroenterologie in Fürth".'
)
