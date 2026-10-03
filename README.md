# Qt5_Python_CHM_HelpViewer
Microsoft Compressed HTML Help File Viewer for Windows 10+

# CHM Viewer – Technische und Anwender-Dokumentation

**Version:** v3 – moderne + Legacy-/Delphi-kompatible Schnittstelle  
**Technik:** Python 3, PyQt5, QtWebEngine, Windows CHM  
**Anwendung:** eigenständiger CHM-Viewer und externer Hilfe-Viewer für andere Anwendungen

---

## Inhaltsverzeichnis

1. [Ziel und Überblick](#1-ziel-und-überblick)
2. [Funktionsumfang](#2-funktionsumfang)
3. [Systemvoraussetzungen](#3-systemvoraussetzungen)
4. [Datei- und Projektstruktur](#4-datei--und-projektstruktur)
5. [Installation](#5-installation)
6. [Programmstart](#6-programmstart)
7. [Benutzeroberfläche](#7-benutzeroberfläche)
8. [Dark Mode](#8-dark-mode)
9. [Persistente Fenster- und Splitter-Geometrie](#9-persistente-fenster--und-splitter-geometrie)
10. [CHM-Dateien öffnen und entpacken](#10-chm-dateien-öffnen-und-entpacken)
11. [Themen, Schlüsselwörter und Favoriten](#11-themen-schlüsselwörter-und-favoriten)
12. [SVG-Unterstützung](#12-svg-unterstützung)
13. [Moderne Kommandozeilenschnittstelle](#13-moderne-kommandozeilenschnittstelle)
14. [Legacy-/Delphi-Kompatibilität](#14-legacy-delphi-kompatibilität)
15. [HTML-Help-Bridge](#15-html-help-bridge)
16. [Themen-String und Context-ID](#16-themen-string-und-context-id)
17. [Priorität bei Hilfeaufrufen](#17-priorität-bei-hilfeaufrufen)
18. [Metainformationen mit JSON](#18-metainformationen-mit-json)
19. [Integration aus Python](#19-integration-aus-python)
20. [Integration aus Delphi](#20-integration-aus-delphi)
21. [Integration aus C/C++](#21-integration-aus-cc)
22. [F1-Kontexthilfe](#22-f1-kontexthilfe)
23. [CHM-Metadaten](#23-chm-metadaten)
24. [MAP- und ALIAS-Dateien](#24-map--und-alias-dateien)
25. [Interne Architektur](#25-interne-architektur)
26. [Klassen- und Funktionsreferenz](#26-klassen--und-funktionsreferenz)
27. [Navigation und URL-Behandlung](#27-navigation-und-url-behandlung)
28. [Sicherheitsmaßnahmen](#28-sicherheitsmaßnahmen)
29. [Favoriten-Speicherung](#29-favoriten-speicherung)
30. [Fehlerbehandlung und Diagnose](#30-fehlerbehandlung-und-diagnose)
31. [Bekannte Grenzen](#31-bekannte-grenzen)
32. [Empfohlene Metadaten-Konvention](#32-empfohlene-metadaten-konvention)
33. [Testplan](#33-testplan)
34. [Verteilung als EXE](#34-verteilung-als-exe)
35. [Erweiterungspunkte](#35-erweiterungspunkte)
36. [Kurzreferenz](#36-kurzreferenz)

---

# 1. Ziel und Überblick

Der CHM Viewer ist eine eigenständige Qt5-Anwendung zur Anzeige klassischer Microsoft-CHM-Hilfedateien. Die eigentliche Darstellung der HTML-Inhalte erfolgt über **QtWebEngine/Chromium** anstelle des alten Microsoft-CHM-Viewers.

Dadurch können moderne HTML-Inhalte und insbesondere lokale SVG-Grafiken innerhalb der entpackten Hilfe angezeigt werden.

Der Viewer verfolgt zwei Ziele:

1. **Moderne eigene Hilfe-Schnittstelle**
   - `--topic`
   - `--context-id`
   - `--language`
   - `--keyword`
   - `--local`

2. **Kompatibilität mit älteren Hilfe-Konzepten**
   - `help.chm::/topic.html`
   - `-mapid`
   - `/context`
   - `-keyword`
   - HTML-Help-Kommandos wie `HH_HELP_CONTEXT`

Beide Varianten werden intern auf dieselbe Navigationslogik abgebildet.

---

# 2. Funktionsumfang

Der aktuelle Viewer bietet:

- Öffnen einer `.chm`-Datei
- Öffnen eines bereits entpackten Hilfe-Verzeichnisses
- automatische CHM-Extraktion
- Themenbaum aus `.hhc`
- Schlüsselwortindex aus `.hhk`
- Auswertung von `.hhp`
- Auswertung von `[MAP]` und `[ALIAS]`
- zusätzliche Suche nach `#define`-Context-IDs in Header-Dateien
- direkte Navigation zu einer lokalen HTML-Seite
- Navigation über Context-ID
- Navigation über Topic-/Wortsuche
- Navigation über Keyword
- Favoriten
- Zurück / Vor / Startseite
- Seiten-Quelltext
- globaler Dark Mode
- persistente Fenstergeometrie
- persistenter Splitter-Zustand
- persistenter Theme-Zustand
- lokale SVG-Unterstützung
- Legacy-/Delphi-kompatible Kommandozeilenargumente
- Source-Level-Delphi-Adapter

---

# 3. Systemvoraussetzungen

## 3.1 Betriebssystem

Der Viewer ist für Windows ausgelegt.

Die CHM-Extraktion verwendet bevorzugt:

```text
hh.exe -decompile
```

Als Fallback kann 7-Zip verwendet werden.

## 3.2 Python

Empfohlen:

```text
Python 3.10 oder neuer
```

Die aktuelle Entwicklung wurde mit Python 3.x erstellt.

## 3.3 Python-Pakete

Erforderlich:

```text
PyQt5
PyQtWebEngine
```

Installation:

```powershell
py -m pip install PyQt5 PyQtWebEngine
```

oder:

```powershell
py -m pip install -r requirements.txt
```

---

# 4. Datei- und Projektstruktur

Das Paket besitzt folgende Struktur:

```text
chmviewer_package_v3_legacy_compat/
│
├── chmviewer.py
├── requirements.txt
├── README.txt
├── helpmeta.example.json
│
└── delphi/
    └── ChmViewerCompat.pas
```

## Bedeutung

### `chmviewer.py`

Hauptprogramm mit:

- Qt5-GUI
- CHM-Extraktion
- Themen-/Keywordparser
- Context-ID-Auswertung
- Navigation
- Theme
- CLI-Kompatibilität

### `requirements.txt`

Python-Abhängigkeiten.

### `helpmeta.example.json`

Beispiel für Metainformationen einer aufrufenden Anwendung.

### `delphi/ChmViewerCompat.pas`

Delphi-Adapter für Source-Level-Kompatibilität.

---

# 5. Installation

## 5.1 Virtuelle Umgebung

Optional:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Danach:

```powershell
py -m pip install -r requirements.txt
```

## 5.2 Funktionstest

```powershell
py chmviewer.py
```

Es erscheint das leere Hauptfenster des Viewers.

---

# 6. Programmstart

## 6.1 Ohne Datei

```powershell
py chmviewer.py
```

## 6.2 CHM direkt öffnen

```powershell
py chmviewer.py help.chm
```

## 6.3 Entpacktes Hilfe-Verzeichnis

```powershell
py chmviewer.py help\
```

## 6.4 Dark Mode erzwingen

```powershell
py chmviewer.py help.chm --dark
```

## 6.5 Light Mode erzwingen

```powershell
py chmviewer.py help.chm --light
```

Ohne `--dark` oder `--light` wird der zuletzt gespeicherte Modus verwendet.

---

# 7. Benutzeroberfläche

Die Anwendung basiert auf `QMainWindow`.

Die grobe Struktur lautet:

```text
QMainWindow
│
├── Menüleiste
├── Navigations-Toolbar
├── CentralWidget
│   └── QSplitter
│       ├── QTabWidget
│       │   ├── Themen
│       │   ├── Schlüsselwörter
│       │   └── Favoriten
│       │
│       └── QWebEngineView
│
└── StatusBar
```

## 7.1 Menü Datei

Enthält:

- Hilfe öffnen …
- Hilfe-Verzeichnis öffnen …
- Programm beenden

## 7.2 Menü Bearbeiten

Enthält:

- Kopieren
- Seiten-Quelltext

## 7.3 Menü Ansicht

Enthält:

- Dark Mode

## 7.4 Menü Hilfe

Enthält:

- Über …

## 7.5 Toolbar

Enthält:

- Hilfe öffnen
- Start
- Zurück
- Vor

---

# 8. Dark Mode

Der Dark Mode gilt für die **gesamte QApplication**.

Damit werden nicht nur HTML-Seiten, sondern auch Qt-Widgets angepasst:

- Hauptfenster
- Menüs
- Toolbar
- Statusbar
- Eingabefelder
- QTreeWidget
- Tabs
- Dialoge
- Buttons
- Quelltextfenster
- Tooltips
- WebEngine-Hintergrund

## 8.1 Umsetzung

Der Viewer benutzt:

```python
QApplication.setPalette(...)
QApplication.setStyleSheet(...)
```

Für den Web-Inhalt wird zusätzlich CSS injiziert.

## 8.2 Persistenz

Der Theme-Zustand wird über `QSettings` gespeichert:

```text
ui/dark_mode
```

---

# 9. Persistente Fenster- und Splitter-Geometrie

Beim Schließen speichert der Viewer:

```text
ui/window_geometry
ui/window_state
ui/main_splitter_state
ui/dark_mode
```

Verwendete Qt-Funktionen:

```python
saveGeometry()
restoreGeometry()

saveState()
restoreState()

QSplitter.saveState()
QSplitter.restoreState()
```

Die Wiederherstellung erfolgt bereits im Konstruktor vor dem ersten sichtbaren `show()`.

Dadurch erscheint das Fenster beim nächsten Start direkt:

- an der alten Position
- in der alten Größe
- mit dem vorherigen Splitter-Verhältnis
- im vorherigen Theme

---

# 10. CHM-Dateien öffnen und entpacken

Eine CHM-Datei wird nicht direkt durch Chromium gelesen.

Stattdessen:

```text
CHM
 │
 ▼
temporäres Verzeichnis
 │
 ├── HTML
 ├── CSS
 ├── JavaScript
 ├── Bilder
 ├── SVG
 ├── HHC
 ├── HHK
 └── HHP
 │
 ▼
QWebEngineView
```

## 10.1 Primärer Extraktor

Unter Windows wird zuerst `hh.exe` gesucht.

Typische Kandidaten:

```text
%WINDIR%\hh.exe
%WINDIR%\System32\hh.exe
%WINDIR%\SysWOW64\hh.exe
```

Aufruf:

```text
hh.exe -decompile <Zielverzeichnis> <Datei.chm>
```

Der Viewer wartet bis zu etwa acht Sekunden auf extrahierte Inhalte.

## 10.2 Fallback

Ist `hh.exe` nicht erfolgreich, wird nach folgenden Programmen gesucht:

```text
7z
7za
7zr
```

Beispiel:

```text
7z x -y -o<Ziel> help.chm
```

## 10.3 Temporäre Dateien

Das entpackte CHM wird in einem temporären Verzeichnis abgelegt.

Beim Schließen wird dieses Verzeichnis bereinigt.

---

# 11. Themen, Schlüsselwörter und Favoriten

## 11.1 Themen

Der Themenbaum wird normalerweise aus einer `.hhc`-Datei gelesen.

Die Sitemap wird mit `HTMLParser` ausgewertet.

Typische Struktur:

```html
<OBJECT type="text/sitemap">
  <param name="Name" value="PRINT">
  <param name="Local" value="basic/print.html">
</OBJECT>
```

## 11.2 Schlüsselwörter

Der Schlüsselwortindex wird aus `.hhk` gelesen.

Auch hier wird das klassische `text/sitemap`-Format verarbeitet.

## 11.3 Fallback ohne HHC

Ist keine Themen-Sitemap vorhanden, durchsucht der Viewer das Hilfeverzeichnis nach:

```text
*.html
*.htm
```

und erzeugt daraus einen einfachen Themenbaum.

---

# 12. SVG-Unterstützung

Die Inhalte werden mit `QWebEngineView` dargestellt.

Daher können lokale SVG-Dateien eingebunden werden:

```html
<img src="images/74ls00.svg" alt="74LS00">
```

Voraussetzung ist, dass die SVG-Datei beim Entpacken Bestandteil der Hilfe ist.

Die Einstellung:

```python
QWebEngineSettings.LocalContentCanAccessFileUrls = True
```

erlaubt lokalen HTML-Dateien Zugriff auf weitere lokale Ressourcen.

Der Remote-Zugriff lokaler Inhalte wird dagegen deaktiviert:

```python
QWebEngineSettings.LocalContentCanAccessRemoteUrls = False
```

---

# 13. Moderne Kommandozeilenschnittstelle

## 13.1 Topic

```powershell
chmviewer.exe help.chm --topic PRINT
```

## 13.2 Topic mit Sprache

```powershell
chmviewer.exe help.chm --topic PRINT --language basic
```

## 13.3 Context-ID

```powershell
chmviewer.exe help.chm --context-id 2101
```

Auch hexadezimale IDs sind möglich:

```powershell
chmviewer.exe help.chm --context-id 0x835
```

## 13.4 Context-ID mit Topic-Fallback

Empfohlen:

```powershell
chmviewer.exe help.chm ^
    --context-id 2101 ^
    --topic PRINT ^
    --language basic
```

Kann die ID nicht aufgelöst werden, steht weiterhin der lesbare Topic-String zur Verfügung.

## 13.5 Direkte HTML-Seite

```powershell
chmviewer.exe help.chm --local basic/print.html
```

## 13.6 Keyword

```powershell
chmviewer.exe help.chm --keyword PRINT
```

## 13.7 Alter Parameter `--word`

Bleibt kompatibel:

```powershell
chmviewer.exe help.chm --word PRINT
```

`--word` ist ein Alias für `--topic`.

---

# 14. Legacy-/Delphi-Kompatibilität

Der Viewer akzeptiert mehrere ältere Schreibweisen.

## 14.1 Klassischer CHM-Pfad

```powershell
chmviewer.exe "help.chm::/basic/print.html"
```

Auch diese Formen werden erkannt:

```text
mk:@MSITStore:help.chm::/basic/print.html
ms-its:help.chm::/basic/print.html
```

## 14.2 Context-ID

```powershell
chmviewer.exe -mapid 2101 help.chm
```

Weitere akzeptierte Aliase:

```text
-mapid
-context
-contextid

/mapid
/context
/contextid
```

## 14.3 Keyword

```powershell
chmviewer.exe -keyword PRINT help.chm
```

oder:

```powershell
chmviewer.exe /keyword PRINT help.chm
```

## 14.4 Direkte Seite

```powershell
chmviewer.exe -topic basic/print.html help.chm
```

oder:

```powershell
chmviewer.exe /topic basic/print.html help.chm
```

Bei Legacy-Aufrufen bedeutet `-topic` beziehungsweise `/topic` einen direkten lokalen Pfad.

Beim modernen Aufruf bedeutet:

```text
--topic
```

dagegen einen lesbaren Suchbegriff.

Dieser Unterschied ist bewusst gewählt.

---

# 15. HTML-Help-Bridge

Der Viewer besitzt zusätzlich eine explizite Bridge für bekannte HTML-Help-Kommandos.

Unterstützt sind derzeit:

```text
HH_DISPLAY_TOPIC  = 0x0000
HH_KEYWORD_LOOKUP = 0x000D
HH_HELP_CONTEXT   = 0x000F
```

## 15.1 HH_HELP_CONTEXT

```powershell
chmviewer.exe help.chm ^
    --hh-command HH_HELP_CONTEXT ^
    --hh-data 2101
```

## 15.2 HH_DISPLAY_TOPIC

```powershell
chmviewer.exe help.chm ^
    --hh-command HH_DISPLAY_TOPIC ^
    --hh-data basic/print.html
```

## 15.3 HH_KEYWORD_LOOKUP

```powershell
chmviewer.exe help.chm ^
    --hh-command HH_KEYWORD_LOOKUP ^
    --hh-data PRINT
```

## 15.4 Numerischer Command

Der Command darf auch numerisch übergeben werden.

Beispiel:

```powershell
chmviewer.exe help.chm --hh-command 0x000F --hh-data 2101
```

---

# 16. Themen-String und Context-ID

Für neue Anwendungen wird empfohlen, **nicht nur eine einzige Information** zu speichern.

Optimal ist:

```text
Topic       = PRINT
Context-ID  = 2101
Language    = basic
Local       = basic/print.html
```

Warum?

### Context-ID

Vorteil:

- stabil
- schnell
- klassisches Hilfe-Konzept
- gut für F1-Hilfe

Nachteil:

- für Menschen nicht lesbar
- Zuordnung muss in CHM-Metadaten vorhanden sein

### Topic

Vorteil:

- lesbar
- funktioniert als Fallback

Nachteil:

- mehrere gleichnamige Themen möglich

### Local

Vorteil:

- eindeutig

Nachteil:

- Pfad kann sich bei Umstrukturierung ändern

### Sprache

Verfeinert einen Topic-Treffer.

---

# 17. Priorität bei Hilfeaufrufen

`set_pending_request()` speichert eine Anfrage.

Beim Öffnen wird sie in folgender Reihenfolge verarbeitet:

```text
1. Local
2. Context-ID / Topic
3. Keyword
4. Topic-Fallback
```

Genauer:

```text
pending_local
    │
    ├─ gefunden → öffnen
    └─ nicht gefunden
          │
          ▼
context_id oder topic
          │
          ├─ Context-ID erfolgreich → öffnen
          ├─ Topic erfolgreich      → öffnen
          └─ kein Treffer
                │
                ▼
keyword
```

---

# 18. Metainformationen mit JSON

Das Paket enthält:

```text
helpmeta.example.json
```

Beispiel:

```json
{
  "viewer": "chmviewer.exe",
  "help_file": "help/c64.chm",
  "topics": {
    "PRINT": {
      "language": "basic",
      "topic": "PRINT",
      "context_id": 2101,
      "local": "basic/print.html"
    },
    "GOTO": {
      "language": "basic",
      "topic": "GOTO",
      "context_id": 2102,
      "local": "basic/goto.html"
    }
  }
}
```

## Empfehlung

Für jedes Hilfethema:

```json
{
  "language": "...",
  "topic": "...",
  "context_id": 0,
  "local": "..."
}
```

---

# 19. Integration aus Python

## 19.1 Einfacher Topic-Aufruf

```python
import subprocess

subprocess.Popen([
    "chmviewer.exe",
    "help/c64.chm",
    "--topic",
    "PRINT",
])
```

## 19.2 Mit Context-ID

```python
subprocess.Popen([
    "chmviewer.exe",
    "help/c64.chm",
    "--topic", "PRINT",
    "--language", "basic",
    "--context-id", "2101",
])
```

## 19.3 Metadaten verwenden

```python
HELP = {
    "PRINT": {
        "language": "basic",
        "context_id": 2101,
        "local": "basic/print.html",
    },
}

def show_help(topic):
    topic = topic.upper()
    meta = HELP.get(topic)

    if not meta:
        return False

    args = [
        "chmviewer.exe",
        "help/c64.chm",
        "--topic", topic,
        "--language", meta["language"],
        "--context-id", str(meta["context_id"]),
    ]

    subprocess.Popen(args)
    return True
```

---

# 20. Integration aus Delphi

Das mitgelieferte Unit:

```text
delphi\ChmViewerCompat.pas
```

definiert:

```pascal
HH_DISPLAY_TOPIC
HH_KEYWORD_LOOKUP
HH_HELP_CONTEXT
```

und folgende Funktionen:

```pascal
ChmViewerTopic(...)
ChmViewerContext(...)
ChmViewerKeyword(...)
ChmViewerHtmlHelp(...)
```

## 20.1 Topic

```pascal
ChmViewerTopic(
  'chmviewer.exe',
  'help\c64.chm',
  'basic\print.html'
);
```

## 20.2 Context-ID

```pascal
ChmViewerContext(
  'chmviewer.exe',
  'help\c64.chm',
  2101
);
```

## 20.3 Keyword

```pascal
ChmViewerKeyword(
  'chmviewer.exe',
  'help\c64.chm',
  'PRINT'
);
```

## 20.4 HTML-Help-artige API

```pascal
ChmViewerHtmlHelp(
  'chmviewer.exe',
  'help\c64.chm',
  HH_HELP_CONTEXT,
  '',
  2101
);
```

Direktes Thema:

```pascal
ChmViewerHtmlHelp(
  'chmviewer.exe',
  'help\c64.chm',
  HH_DISPLAY_TOPIC,
  'basic\print.html',
  0
);
```

---

# 21. Integration aus C/C++

Der Viewer kann mit `CreateProcessW`, `ShellExecuteW` oder ähnlichen Mechanismen gestartet werden.

Beispiel mit `ShellExecuteW`:

```cpp
#include <windows.h>

void ShowHelpContext()
{
    ShellExecuteW(
        nullptr,
        L"open",
        L"chmviewer.exe",
        L"\"help\\c64.chm\" --context-id 2101 --topic PRINT",
        nullptr,
        SW_SHOWNORMAL
    );
}
```

Direktes Thema:

```cpp
ShellExecuteW(
    nullptr,
    L"open",
    L"chmviewer.exe",
    L"\"help\\c64.chm::/basic/print.html\"",
    nullptr,
    SW_SHOWNORMAL
);
```

---

# 22. F1-Kontexthilfe

Ein typischer Ablauf in einer IDE oder einem Editor:

```text
Benutzer drückt F1
       │
       ▼
Wort unter Cursor bestimmen
       │
       ▼
Metadaten nachschlagen
       │
       ├── Topic
       ├── Context-ID
       ├── Sprache
       └── Local
       │
       ▼
chmviewer.exe starten
```

Beispiel:

```python
def handle_f1(word):
    word = word.strip().upper()

    args = [
        "chmviewer.exe",
        "help/c64.chm",
        "--topic", word,
        "--language", "basic",
    ]

    context_id = BASIC_HELP_IDS.get(word, 0)
    if context_id:
        args += ["--context-id", str(context_id)]

    subprocess.Popen(args)
```

---

# 23. CHM-Metadaten

Die wichtigsten klassischen Dateien:

```text
*.hhp  Projekt
*.hhc  Contents / Themen
*.hhk  Index / Schlüsselwörter
*.h    Context-ID-Konstanten
```

## 23.1 HHP

Aus `[OPTIONS]` werden insbesondere berücksichtigt:

```text
Contents file
Index file
Default topic
```

## 23.2 HHC

Erzeugt den Themenbaum.

## 23.3 HHK

Erzeugt den Schlüsselwortbaum.

---

# 24. MAP- und ALIAS-Dateien

Für numerische Context-IDs werden `[MAP]` und `[ALIAS]` aus der HHP ausgewertet.

Beispiel:

```ini
[MAP]
#define IDH_PRINT 2101
#define IDH_GOTO  2102

[ALIAS]
IDH_PRINT=basic/print.html
IDH_GOTO=basic/goto.html
```

Alternativ können Definitionen auch in Header-Dateien stehen:

```c
#define IDH_PRINT 2101
#define IDH_GOTO  2102
```

Der Viewer durchsucht dazu `*.h` im entpackten Hilfeverzeichnis.

Das Ergebnis ist intern:

```python
{
    2101: "basic/print.html",
    2102: "basic/goto.html"
}
```

---

# 25. Interne Architektur

## 25.1 Datenfluss

```text
Kommandozeile
      │
      ▼
normalize_legacy_argv()
      │
      ▼
parse_args()
      │
      ├── modern
      ├── legacy
      └── HH bridge
      │
      ▼
MainWindow.set_pending_request()
      │
      ▼
CHM öffnen / entpacken
      │
      ▼
HHC / HHK / HHP / MAP / ALIAS lesen
      │
      ▼
apply_pending_help_request()
      │
      ▼
QWebEngineView
```

## 25.2 GUI-Struktur

```text
MainWindow
├── Actions
├── MenuBar
├── ToolBar
├── QSplitter
│   ├── QTabWidget
│   │   ├── ChmSearchTab Topics
│   │   ├── ChmSearchTab Keywords
│   │   └── ChmSearchTab Favorites
│   └── QWebEngineView
└── QStatusBar
```

---

# 26. Klassen- und Funktionsreferenz

## `ChmSitemapEntry`

Dataclass:

```python
title: str
local: str
children: List[ChmSitemapEntry]
```

Repräsentiert einen HHC-/HHK-Eintrag.

---

## `ChmSitemapParser`

Parser für klassische HTML-Help-Sitemaps.

Wichtige Methoden:

```python
handle_starttag()
handle_endtag()
```

Liest insbesondere:

```html
<object type="text/sitemap">
<param name="Name" ...>
<param name="Local" ...>
```

---

## `ChmExtractor`

Verantwortlich für das Entpacken.

Methode:

```python
ChmExtractor.extract(source, destination)
```

Priorität:

```text
hh.exe
   ↓
7-Zip
```

---

## `ChmSearchTab`

Wiederverwendbarer Tab mit:

- `QLineEdit`
- Suchbutton
- `QTreeWidget`

Signal:

```python
search_requested = pyqtSignal(str)
```

---

## `ChmWebPage`

Unterklasse von:

```python
QWebEnginePage
```

Behandelt:

- interne `mk:`-/`ms-its:`-Links
- externe HTTP-/HTTPS-/Mail-Links

Externe Links werden über:

```python
QDesktopServices.openUrl()
```

geöffnet.

---

## `ChmSourceDialog`

Zeigt den HTML-Quelltext der aktuellen Seite.

---

## `MainWindow`

Zentrale Hauptklasse.

### Wichtige Methoden

```python
open_chm()
open_help_directory()

read_metadata()
populate_tree()

load_local()
open_context_topic()
open_keyword_topic()

set_pending_request()
apply_pending_help_request()

add_current_favorite()
remove_current_favorite()

set_dark_mode()

save_ui_state()
restore_ui_state()
```

---

## `clean_chm_local()`

Normalisiert interne CHM-Pfade.

Verarbeitet unter anderem:

```text
mk:@MSITStore:
ms-its:
its:
::/
#
URL-Encoding
Backslashes
```

Verhindert außerdem Pfade mit `..`.

---

## `resolve_chm_path()`

Löst einen internen Pfad im entpackten CHM auf.

Enthält einen case-insensitiven Fallback.

Das ist wichtig, weil CHM-Hilfen häufig inkonsistente Groß-/Kleinschreibung enthalten.

---

## `read_chm_context_map()`

Erzeugt:

```python
Dict[int, str]
```

aus:

- `[MAP]`
- `[ALIAS]`
- `*.h`

---

## `normalize_legacy_argv()`

Übersetzt bekannte alte Argumente.

Beispiel:

```text
/context    -> --context-id
/mapid      -> --context-id
/keyword    -> --keyword
/topic      -> --local
```

---

## `split_chm_reference()`

Zerlegt:

```text
help.chm::/basic/print.html
```

in:

```text
CHM-Datei = help.chm
Local     = basic/print.html
```

---

## `normalize_hh_command()`

Akzeptiert:

```text
HH_HELP_CONTEXT
HELP_CONTEXT
CONTEXT
0x000F
15
```

---

# 27. Navigation und URL-Behandlung

## 27.1 Lokale Seiten

Interne Seiten werden mit:

```python
QUrl.fromLocalFile(...)
```

geladen.

## 27.2 Fragmente

Auch Anchor-Links werden unterstützt:

```text
basic/print.html#syntax
```

## 27.3 Externe Links

Folgende Schemes können extern geöffnet werden:

```text
http
https
mailto
```

## 27.4 Remote-Inhalte

Die Einstellung:

```python
LocalContentCanAccessRemoteUrls = False
```

verhindert, dass eine lokale Hilfeseite beliebig Remote-Ressourcen lädt.

---

# 28. Sicherheitsmaßnahmen

Der Viewer enthält mehrere Schutzmaßnahmen.

## 28.1 Pfadnormalisierung

`clean_chm_local()` verwirft:

```text
../
```

Dadurch sollen Pfade nicht aus dem entpackten Root herausführen.

## 28.2 Root-Prüfung

`resolve_chm_path()` kontrolliert über `Path.resolve()` und `relative_to()`, dass die Datei im Hilfe-Root liegt.

## 28.3 Remote-Zugriff

Lokale Seiten dürfen nicht automatisch Remote-URLs nachladen.

## 28.4 Externe Links

HTTP/HTTPS/Mailto werden aus der WebEngine heraus an das Betriebssystem übergeben.

---

# 29. Favoriten-Speicherung

Favoriten werden mit `QSettings` gespeichert.

Für jede Hilfe gibt es einen separaten Schlüssel.

Dieser wird aus dem Hilfe-Pfad erzeugt:

```text
SHA-256(CHM-Pfad)
```

Schema:

```text
chm/favorites/<hash>
```

Gespeicherter Inhalt:

```json
[
  {
    "title": "PRINT",
    "local": "basic/print.html"
  }
]
```

Dadurch vermischen sich Favoriten verschiedener Hilfedateien nicht.

---

# 30. Fehlerbehandlung und Diagnose

## 30.1 PyQt fehlt

Meldung:

```text
PyQt5 / PyQtWebEngine fehlt.
```

Abhilfe:

```powershell
py -m pip install PyQt5 PyQtWebEngine
```

## 30.2 CHM kann nicht entpackt werden

Prüfen:

```text
hh.exe vorhanden?
7z vorhanden?
CHM beschädigt?
Schreibrecht im Temp-Verzeichnis?
```

## 30.3 Topic wird nicht gefunden

Prüfen:

1. Ist es in `.hhc` oder `.hhk` vorhanden?
2. Entspricht der Dateiname dem Topic?
3. Stimmt `--language`?
4. Gibt es eine Context-ID?
5. Ist der Local-Pfad korrekt?

## 30.4 Context-ID wird nicht gefunden

Prüfen:

```ini
[MAP]
...
[ALIAS]
...
```

sowie Header-Dateien.

## 30.5 SVG wird nicht angezeigt

Prüfen:

- SVG in CHM enthalten?
- relativer Pfad korrekt?
- Datei nach Extraktion vorhanden?
- HTML verweist auf lokalen Pfad?

---

# 31. Bekannte Grenzen

## 31.1 Kein echter Ersatz für `hhctrl.ocx`

Der aktuelle Delphi-Adapter ist **Source-Level-Kompatibilität**.

Das bedeutet:

Eine Delphi-Anwendung, die neu kompiliert wird, kann:

```pascal
ChmViewerContext(...)
```

verwenden.

Eine bereits kompilierte EXE, die intern direkt:

```text
HtmlHelpA()
HtmlHelpW()
hhctrl.ocx
```

aufruft, wird nicht automatisch umgeleitet.

Dafür wäre ein zusätzlicher nativer Proxy nötig.

## 31.2 Noch nicht alle HTML-Help-Kommandos

Aktuell werden explizit unterstützt:

```text
HH_DISPLAY_TOPIC
HH_KEYWORD_LOOKUP
HH_HELP_CONTEXT
```

Andere Kommandos benötigen zusätzliche Adapterlogik.

## 31.3 CHM-Extraktion

`hh.exe -decompile` ist ein pragmatischer Weg.

Ungewöhnliche oder beschädigte CHMs können trotzdem Probleme verursachen.

---

# 32. Empfohlene Metadaten-Konvention

Für das d64_dism-/dBase2Many-Projekt empfiehlt sich eine zentrale Hilfe-Metadatendatei.

Beispiel:

```json
{
  "basic": {
    "PRINT": {
      "context_id": 2101,
      "local": "basic/print.html"
    },
    "GOTO": {
      "context_id": 2102,
      "local": "basic/goto.html"
    }
  },
  "pascal": {
    "WRITELN": {
      "context_id": 3101,
      "local": "pascal/writeln.html"
    }
  }
}
```

Vorteil:

```text
Editor
Compiler
GUI
F1-Hilfe
CHM
```

greifen auf dieselben IDs zu.

---

# 33. Testplan

## 33.1 Grundstart

```text
[ ] Viewer startet ohne Datei
[ ] Viewer startet mit CHM
[ ] Viewer startet mit Verzeichnis
```

## 33.2 Theme

```text
[ ] Dark Mode färbt gesamte Anwendung
[ ] Light Mode funktioniert
[ ] Theme wird gespeichert
[ ] Theme ist beim Neustart sofort aktiv
```

## 33.3 Geometrie

```text
[ ] Fensterposition speichern
[ ] Fenstergröße speichern
[ ] maximierter Zustand speichern
[ ] Splitterposition speichern
[ ] Wiederherstellung vor erstem Anzeigen
```

## 33.4 CHM

```text
[ ] HHP lesen
[ ] HHC lesen
[ ] HHK lesen
[ ] Default Topic
[ ] SVG darstellen
[ ] relative Bilder darstellen
```

## 33.5 Context

```text
[ ] --topic PRINT
[ ] --word PRINT
[ ] --context-id 2101
[ ] --context-id + --topic
[ ] --keyword PRINT
[ ] --local basic/print.html
```

## 33.6 Legacy

```text
[ ] help.chm::/basic/print.html
[ ] -mapid 2101 help.chm
[ ] /context 2101 help.chm
[ ] -keyword PRINT help.chm
[ ] /topic basic/print.html help.chm
```

## 33.7 HTML Help

```text
[ ] HH_HELP_CONTEXT
[ ] HH_DISPLAY_TOPIC
[ ] HH_KEYWORD_LOOKUP
```

## 33.8 Favoriten

```text
[ ] hinzufügen
[ ] Doppelanlage verhindern
[ ] entfernen
[ ] Neustart
[ ] getrennte Favoriten pro CHM
```

---

# 34. Verteilung als EXE

Eine mögliche PyInstaller-Erzeugung:

```powershell
pyinstaller ^
    --noconsole ^
    --onefile ^
    --name chmviewer ^
    chmviewer.py
```

Bei QtWebEngine kann eine `--onedir`-Variante robuster sein:

```powershell
pyinstaller ^
    --noconsole ^
    --onedir ^
    --name chmviewer ^
    chmviewer.py
```

Nach dem Build sollte geprüft werden:

```text
QtWebEngineProcess
resources
translations
platforms
```

PyInstaller sammelt diese Komponenten normalerweise über die Qt-Hooks ein.

Für deine Anwendung bietet sich an:

```text
Programm.exe
chmviewer.exe
help\
    c64.chm
```

---

# 35. Erweiterungspunkte

## 35.1 Nativer `HtmlHelp`-Proxy

Für Binärkompatibilität mit bereits kompilierten Anwendungen könnte später eine native DLL entstehen.

Denkbares Konzept:

```text
alte Anwendung
     │
     ▼
HtmlHelpW(...)
     │
     ▼
Kompatibilitäts-DLL
     │
     ▼
chmviewer.exe
```

## 35.2 Single-Instance-Viewer

Derzeit startet jeder Hilfeaufruf einen eigenen Prozess.

Eine spätere Erweiterung könnte:

- vorhandene Instanz erkennen
- Topic über Named Pipe / Local Socket senden
- bestehendes Fenster nach vorne holen

## 35.3 Weitere HH-Kommandos

Mögliche Ergänzungen:

```text
HH_DISPLAY_INDEX
HH_DISPLAY_SEARCH
HH_SET_WIN_TYPE
HH_GET_WIN_TYPE
```

## 35.4 Programmierschnittstelle

Zusätzlich zur Kommandozeile könnte eine IPC-Schnittstelle eingeführt werden:

```json
{
  "command": "help",
  "file": "c64.chm",
  "topic": "PRINT",
  "context_id": 2101
}
```

## 35.5 Mehrsprachigkeit

Die vorhandene `language`-Information kann später zur Auswahl unterschiedlicher Hilfe-Dateien oder Sprachpfade erweitert werden.

---

# 36. Kurzreferenz

## Modern

```powershell
chmviewer.exe help.chm --topic PRINT
```

```powershell
chmviewer.exe help.chm --topic PRINT --language basic
```

```powershell
chmviewer.exe help.chm --context-id 2101 --topic PRINT
```

```powershell
chmviewer.exe help.chm --local basic/print.html
```

```powershell
chmviewer.exe help.chm --keyword PRINT
```

## Rückwärtskompatibel

```powershell
chmviewer.exe help.chm --word PRINT
```

## Legacy

```powershell
chmviewer.exe "help.chm::/basic/print.html"
```

```powershell
chmviewer.exe -mapid 2101 help.chm
```

```powershell
chmviewer.exe /context 2101 help.chm
```

```powershell
chmviewer.exe -keyword PRINT help.chm
```

## HTML Help Bridge

```powershell
chmviewer.exe help.chm --hh-command HH_HELP_CONTEXT --hh-data 2101
```

```powershell
chmviewer.exe help.chm --hh-command HH_DISPLAY_TOPIC --hh-data basic/print.html
```

```powershell
chmviewer.exe help.chm --hh-command HH_KEYWORD_LOOKUP --hh-data PRINT
```

---

# Schlussbemerkung

Der CHM Viewer verbindet klassische Windows-Hilfe-Strukturen mit einer modernen QtWebEngine-basierten Darstellung.

Der entscheidende Architekturpunkt ist die Trennung zwischen:

```text
externer Aufrufsyntax
        │
        ▼
Normalisierung
        │
        ▼
interne Hilfe-Anfrage
        │
        ▼
gemeinsame Navigation
```

Dadurch können moderne Anwendungen und ältere Delphi-/HTML-Help-orientierte Programme dieselbe Hilfedatenbasis verwenden, ohne dass zwei getrennte Viewer gepflegt werden müssen.
