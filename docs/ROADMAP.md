# Wohin der Life Agent wachsen kann

Diese Datei hält fest, was bewusst **noch nicht** gebaut ist, was es kosten
würde und was es wirklich bringt. Reihenfolge = Empfehlung.

---

## Stufe 1 – fertig (aktueller Stand)

- Verträge, Abos, Versicherungen, Mitgliedschaften und Anmeldungen erfassen
- Fristen- und Laufzeitrechnung inklusive automatischer Verlängerung
- CSV-Import von Kontoumsätzen mit Spaltenerkennung und Dublettenschutz
- Automatische Zuordnung Buchung → Vertrag, mit lernenden Regeln
- Erkennung unbekannter Abos, Preiserhöhungen, ausbleibender Zahlungen,
  Doppelverträge und zu hoher Fixkostenquote
- Kündigungsschreiben-Generator mit Checkliste
- Tagesübersicht, Push über ntfy oder E-Mail, tägliche Sicherung

---

## Stufe 2 – naheliegend, hoher Nutzen

### Dokumentenablage pro Vertrag
PDF-Rechnungen und Vertragsunterlagen direkt am Vertrag speichern.
*Aufwand: klein. Nutzen: groß* – beim Kündigen oder Reklamieren hat man alles an einem Ort.

### Mehrere Personen / Haushalt
Ein zweites Profil für Partnerin oder Partner, gemeinsame Verträge kennzeichnen.
*Aufwand: mittel* (Modell und Auswertungen bekommen eine Zuordnung).

### Fristen in den Kalender
Ein `.ics`-Abo, das der Handy-Kalender abholt. Erinnerungen dort, wo man ohnehin hinschaut.
*Aufwand: klein.*

### Kategorien-Budgets
Pro Bereich ein Monatsbudget setzen, bei Überschreitung meldet sich der Buddy.
*Aufwand: klein bis mittel.*

---

## Stufe 3 – möglich, aber mit Nebenwirkungen

### Automatischer Bankabruf (statt CSV)
Technisch geht das über **FinTS/HBCI** (funktioniert nur bei deutschen Banken,
wird zunehmend eingeschränkt) oder über einen **lizenzierten Anbieter** wie
finAPI oder Tink.

- Direkter Zugriff auf Kontodaten ist in der EU nach PSD2 erlaubnispflichtig.
  Als Privatperson für den Eigenbedarf ist FinTS in Ordnung; sobald andere
  Menschen die App nutzen, wird es ein regulatorisches Thema.
- Ein Anbieter-Zugang kostet Geld und bedeutet: Kontodaten laufen über einen Dritten.
- **Empfehlung:** erst bauen, wenn der monatliche CSV-Import wirklich stört.
  Der Gewinn ist Bequemlichkeit, nicht Funktion.

### Postfach-Auswertung
Rechnungen und Vertragsbestätigungen automatisch aus dem E-Mail-Postfach lesen
(IMAP mit App-Passwort oder Gmail-OAuth).

- Sehr wirkungsvoll: Preiserhöhungen stehen oft zuerst in der E-Mail, nicht im Kontoauszug.
- Aber: Vollzugriff auf das Postfach ist der größte denkbare Eingriff in die Privatsphäre.
- **Empfehlung:** nur mit klar begrenztem Zugriff (ein eigener Ordner, in den du
  Vertrags-Mails verschiebst) statt „lies alles“.

### Sprachliche Bedienung
Eingaben wie „Netflix kostet ab Januar 17,99“ per Sprache oder Chatfeld, die der
Agent in Vertragsänderungen übersetzt.

- Braucht ein Sprachmodell. Lokal (Ollama) bleibt alles privat, kostet aber Rechenleistung;
  über eine API ist es schneller, dann verlassen Vertragsdaten das Gerät.
- **Empfehlung:** als Zusatz, nie als einziger Weg. Formulare sind bei Geld verlässlicher.

---

## Bewusst nicht geplant

| Idee | Warum nicht |
|---|---|
| **Automatisch kündigen** | Eine Kündigung ist eine rechtsverbindliche Erklärung. Ein Fehlgriff der Automatik kostet den Anschluss, nicht nur Geld. Der Agent bereitet vor, der Mensch entscheidet. |
| **Tarifvergleich mit Provisionen** | Sobald Empfehlungen vergütet werden, ist der Agent nicht mehr auf der Seite des Nutzers. |
| **Zentrale Cloud für alle Nutzer** | Eine Datenbank mit den Verträgen vieler Menschen ist ein lohnendes Angriffsziel. Lokal ist hier die stärkere Architektur. |
| **Scoring / Bonitätsbewertung** | Heikle Daten, fragwürdiger Nutzen für den Einzelnen. |

---

## Wenn daraus ein Produkt werden soll

1. **Zuerst selbst nutzen.** Drei Monate echter Alltag zeigen mehr als jede Planung.
2. **Zwei bis drei Testnutzer** aus dem Umfeld – am ehesten stolpern sie beim Import.
3. **Erst dann** über Verteilung nachdenken. Eine fertige `.exe`/`.app` ohne
   sichtbares Terminal ist der größte Schritt Richtung „normale Nutzer“
   (PyInstaller oder Tauri-Hülle).
4. **Datenschutz bleibt das Verkaufsargument.** „Läuft auf deinem Gerät“ ist
   gegenüber Cloud-Diensten der stärkste Unterschied – nicht die Funktionsliste.
