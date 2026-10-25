# Datenschutz und Regulatorik

Praxis-Lotse ist eine Demo. Diese Seite beschreibt, welche Entscheidungen in
der Architektur bereits getroffen sind und was für einen produktiven Einsatz
noch fehlt. Sie ist eine fachliche Einschätzung, keine Rechtsberatung.

## Bereits in der Architektur verankert

| Prinzip | Umsetzung | Spec |
|---|---|---|
| Keine echten Daten in der Demo | alle Standorte und Dokumente in `data/` sind fiktiv | – |
| Datenminimierung gegenüber dem LLM | Name, Geburtsdatum und Telefon für Terminanfragen werden über ein Formular direkt an die Termin-API gesendet, nie an das Sprachmodell | 005, 008 |
| Keine personenbezogenen Daten in Logs | zentrale `redact()`-Funktion für Telefonnummern, E-Mail, Geburtsdaten | 006 |
| Embeddings lokal | Dokumente und Fragen werden lokal vektorisiert, nicht bei einem externen Dienst | 003 |
| LLM selbst betrieben | in der Demo läuft das Sprachmodell lokal über Ollama; Chat-Inhalte verlassen den Rechner nicht. Der Anbieter ist per Konfiguration austauschbar (Ollama, Azure OpenAI, Anthropic) | 004 |
| Speicherbegrenzung | Terminanfragen werden nach 30 Tagen automatisch gelöscht | 005 |
| Einwilligung | Terminanfrage nur mit bestätigter Datenschutz-Einwilligung | 005 |
| Transparenz (EU AI Act, Art. 50) | sichtbarer Hinweis, dass man mit einem KI-System spricht | 006, 008 |
| Keine medizinische Beratung | Leitplanken im Systemprompt, regelbasierte Notfallerkennung vor dem LLM | 006 |

## Einordnung EU AI Act

Ein Assistent für Standortauskunft, organisatorische Patienteninformationen
und Terminanfragen ist nach unserer Einschätzung **kein Hochrisiko-System**.
Es gilt die Transparenzpflicht für Systeme, die mit Menschen interagieren
(Art. 50 Abs. 1). Würde der Assistent medizinisch triagieren oder Diagnosen
vorschlagen, wäre neu zu prüfen, ob er ein Medizinprodukt (MDR) und damit
ein Hochrisiko-System ist. Deshalb ist genau das per Spec ausgeschlossen.

## Für den Produktivbetrieb noch offen

- **Modellwahl:** Abwägung zwischen selbst betriebenem Modell (volle Datenhoheit,
  eigene GPU-Kosten, geringere Qualität) und Cloud-Modell in der EU (z. B. Azure
  OpenAI in einer EU-Region; dann AV-Vertrag). Die Eval (Spec 007) liefert dafür
  vergleichbare Zahlen.
- **Besondere Kategorien (Art. 9 DSGVO):** Schon eine Frage wie „Ich brauche
  einen Termin beim Gastroenterologen" kann Gesundheitsdaten enthalten.
  Rechtsgrundlage, Datenschutz-Folgenabschätzung und Löschkonzept mit dem
  Datenschutzbeauftragten klären.
- **Schweigepflicht (§ 203 StGB):** Anbieter als „mitwirkende Personen"
  vertraglich verpflichten.
- **Anbindung an echte Systeme:** Termin-API gegen das tatsächliche
  Terminsystem bzw. PVS, mit Authentifizierung und Protokollierung.
- **Betrieb:** Monitoring, Kostenlimits pro Tag, Rate Limiting gegen Missbrauch.
