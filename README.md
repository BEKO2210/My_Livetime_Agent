# Life Agent

**Dein persönlicher Buddy für Verträge, Abos und Geld.**

Life Agent behält im Blick, was du im Alltag leicht vergisst: wann eine
Kündigungsfrist abläuft, welches Abo du eigentlich gar nicht mehr nutzt, wo der
Preis heimlich gestiegen ist und wie viel von deinem Einkommen jeden Monat schon
verplant ist.

Die App läuft **auf deinem eigenen Rechner**. Es gibt kein Konto, keine
Anmeldung und keinen Server im Internet. Deine Kontodaten bleiben bei dir.

---

## In 3 Minuten startklar

### Mac / Linux

```bash
./start.sh
```

### Windows

Doppelklick auf **`start.bat`**

Beim ersten Start richtet sich die App selbst ein (dauert ein bis zwei Minuten).
Danach öffnet sich dein Browser mit der Übersicht. Zum Beenden: Fenster
schließen oder `Strg + C`.

> Du brauchst nur **Python 3** auf dem Rechner. Falls es fehlt:
> [python.org/downloads](https://www.python.org/downloads/) – unter Windows beim
> Installieren den Haken bei *„Add Python to PATH“* setzen.

### Erst mal nur ausprobieren?

```bash
./start.sh --beispiel     # legt Beispieldaten an
./start.sh                # und dann ansehen
```

Die Beispieldaten löschst du, indem du die Datei `data/lifeagent.db` entfernst.

---

## Was der Buddy für dich tut

| Er meldet sich, wenn … | Warum das Geld spart |
|---|---|
| **eine Kündigungsfrist ausläuft** | Ein verpasster Termin verlängert den Vertrag oft um ein ganzes Jahr. |
| **du ein Abo zahlst, das nirgends erfasst ist** | Aus deinen Kontoumsätzen erkennt er wiederkehrende Abbuchungen – auch die, die du vergessen hast. |
| **ein Preis gestiegen ist** | Bei Preiserhöhungen hast du häufig ein Sonderkündigungsrecht – aber nur kurz. |
| **eine erwartete Abbuchung ausbleibt** | Hinweis auf Rücklastschrift, Zahlungsprobleme oder fehlende Umsätze. |
| **du mehrfach für dasselbe zahlst** | Zwei Streaming-Dienste, zwei Cloud-Speicher – fällt im Alltag nicht auf. |
| **deine Fixkosten zu viel vom Einkommen binden** | Zeigt dir früh, wenn der Spielraum eng wird. |

Dazu gibt es ein **Kündigungsschreiben auf Knopfdruck**: fertiger Text mit dem
richtigen Termin, zum Kopieren und Abschicken.

---

## So arbeitest du damit

### 1. Verträge eintragen

**Verträge → Vertrag hinzufügen.** Pflicht ist nur der Name. Richtig nützlich
wird es mit diesen vier Angaben:

- **Vertragsbeginn** – Grundlage für jede Fristberechnung
- **Mindestlaufzeit** in Monaten (z. B. 24)
- **Verlängerung** in Monaten (`0` = läuft danach unbefristet weiter – seit
  März 2022 bei neuen Verträgen der Normalfall)
- **Kündigungsfrist** in Monaten oder Tagen (z. B. 3 Monate)

Daraus rechnet der Agent aus, bis wann du spätestens kündigen musst – und
erinnert dich rechtzeitig.

### 2. Kontoumsätze importieren

**Import → CSV-Datei hochladen.** Im Online-Banking auf *Umsätze* → *Export* →
*CSV*. Nimm beim ersten Mal ruhig **12 Monate**, dann erkennt der Agent auch
jährliche Zahlungen.

Getestet mit Exporten von Sparkasse, DKB, ING, Comdirect und N26. Spalten werden
automatisch erkannt, doppelte Buchungen übersprungen, bekannte Anbieter direkt
einsortiert.

### 3. Zuordnen lassen

Buchungen landen automatisch beim passenden Vertrag, wenn der Anbietername
passt. Wo das nicht klappt, wählst du den Vertrag einmal von Hand aus und hakst
**„merken“** an – ab dann macht der Agent es selbst.

### 4. Erinnern lassen

**Einstellungen → Benachrichtigungen.** Drei Möglichkeiten:

- **nur in der App** (Standard) – nichts verlässt deinen Rechner
- **Push aufs Handy** über [ntfy](https://ntfy.sh): App installieren, ein
  eigenes Thema ausdenken (z. B. `lifeagent-x7k2m9`), hier eintragen, in der App
  abonnieren. Kostenlos, keine Anmeldung.
  *Wähle etwas Unratbares – wer das Thema kennt, kann mitlesen.*
- **E-Mail** über deinen eigenen SMTP-Server

Solange die App läuft, prüft sie einmal täglich alles durch und meldet sich nur,
wenn es etwas Neues gibt.

---

## Deine Daten

Alles liegt in **einer einzigen Datei**: `data/lifeagent.db`.

- **Sichern:** Datei kopieren – fertig. Oder *Einstellungen → Sicherung herunterladen*.
- **Automatisch:** einmal täglich landet eine Kopie in `data/backups/` (14 Tage).
- **Umziehen:** Datei auf den neuen Rechner kopieren.
- **Löschen:** Datei löschen.

Es gibt keine Cloud, keine Telemetrie und keinen Account. Die einzige
Internetverbindung entsteht, wenn *du* Push-Nachrichten oder E-Mail einschaltest.

**Bitte keine Passwörter in die Notizfelder schreiben** – die Datei ist nicht
verschlüsselt. Kundennummern sind unkritisch, Zugangsdaten gehören in einen
Passwortmanager.

---

## Weitere Befehle

```bash
./start.sh --briefing        # Tagesübersicht im Terminal
./start.sh --pruefen         # einmal prüfen und benachrichtigen
./start.sh --beispiel        # Beispieldaten anlegen
./start.sh --port 9000       # anderer Port
./start.sh --kein-browser    # ohne Browserfenster starten
```

### Dauerhaft laufen lassen (optional)

Mit Docker:

```bash
docker compose up -d        # danach: http://localhost:8777
```

Oder per `cron`, wenn du nur die tägliche Prüfung willst:

```cron
0 8 * * *  cd /pfad/zum/projekt && ./start.sh --pruefen
```

---

## Was der Agent *nicht* macht

Ehrlichkeit vor Marketing:

- **Er liest keine Bankkonten automatisch aus.** Direkter Kontozugriff ist in
  Europa lizenzpflichtig (PSD2). Der CSV-Import dauert eine Minute im Monat und
  kommt ohne Zugangsdaten aus.
- **Er durchsucht nicht dein E-Mail-Postfach.** Möglich, aber ein großer
  Eingriff – kommt nur, wenn du es ausdrücklich willst (siehe `docs/ROADMAP.md`).
- **Er kündigt nicht selbstständig.** Er bereitet die Kündigung vor; den Klick
  machst du. Automatisches Kündigen im Namen des Nutzers ist rechtlich heikel.
- **Er ist keine Rechtsberatung.** Fristen und Textvorlagen sind nach gängigen
  Regeln berechnet – prüf im Zweifel deinen Vertrag.

---

## Für Neugierige: wie es gebaut ist

| Bereich | Technik |
|---|---|
| Sprache | Python 3.10+ |
| Web | FastAPI + Jinja2, serverseitig gerendert, kein Build-Schritt |
| Daten | SQLite über SQLAlchemy, eine Datei |
| Hintergrund | APScheduler im selben Prozess |
| Tests | pytest |

```
lifeagent/
├── dates.py            Fristen-, Laufzeit- und Zahlungsrechnung
├── money.py            Beträge in Cent, deutsche Schreibweise
├── models.py           Vertrag, Buchung, Regel, Hinweis, Einstellung
├── services/
│   ├── importer.py     CSV-Erkennung für Bank-Exporte
│   ├── matching.py     Buchung → Vertrag
│   ├── knowledge.py    eingebautes Anbieterwissen (lokal)
│   ├── insights.py     die Prüfungen des Buddys
│   ├── finance.py      Auswertungen
│   ├── letters.py      Kündigungsschreiben
│   ├── briefing.py     Tagesübersicht
│   └── notify.py       ntfy / E-Mail
├── web/                Oberfläche
└── scheduler.py        täglicher Lauf
```

Tests laufen mit:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

---

## Lizenz

Privates Projekt. Nutzung auf eigene Verantwortung.
