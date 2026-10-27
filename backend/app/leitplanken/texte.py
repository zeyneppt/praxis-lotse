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
