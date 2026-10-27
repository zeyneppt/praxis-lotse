"""Logging-Konfiguration mit Redaktion personenbezogener Daten (Spec 006)."""

import logging
import re
import sys

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATUM = re.compile(r"(?<!\d)\d{1,2}\.\d{1,2}\.\d{4}(?!\d)|(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
# Ziffern, getrennt durch Leerzeichen, Bindestrich, Schrägstrich oder Klammern;
# ab 6 Ziffern gilt die Folge als Telefonnummer (wie in der Terminanfrage). Teile von
# UUIDs und Bezeichnern (Bindestrich oder Buchstaben direkt daneben) bleiben unverändert.
_TELEFON = re.compile(r"(?<![\w.-])(?:\+|\()?\d[\d ()/\-]{4,}\d(?![\w-])")
_MIN_TELEFON_ZIFFERN = 6


def _telefon(treffer: re.Match[str]) -> str:
    ziffern = sum(z.isdigit() for z in treffer.group())
    return "[TELEFON]" if ziffern >= _MIN_TELEFON_ZIFFERN else treffer.group()


def redact(text: str) -> str:
    """Ersetzt E-Mail-Adressen, Datumsangaben und Telefonnummern durch Platzhalter."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _DATUM.sub("[DATUM]", text)
    return _TELEFON.sub(_telefon, text)


class RedactFilter(logging.Filter):
    """Wendet `redact()` auf Nachricht und Ausnahmetext jedes Log-Eintrags an."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        if record.exc_info:
            formatter = logging.Formatter()
            record.exc_text = redact(formatter.formatException(record.exc_info))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def configure_logging() -> None:
    """Root-Handler mit Format und Filter; der Filter hängt auch an den Uvicorn-Handlern."""
    # Uvicorn konfiguriert nur seine eigenen Logger; ohne Root-Handler fehlten die App-Logs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:     %(name)s: %(message)s",
        stream=sys.stderr,
    )
    filter_ = RedactFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactFilter) for f in handler.filters):
                handler.addFilter(filter_)
