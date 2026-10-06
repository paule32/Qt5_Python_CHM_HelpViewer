CHM Viewer v3 – moderne + Legacy-/Delphi-kompatible Schnittstelle

MODERNES FORMAT
---------------
Topic:
    py chmviewer.py help.chm --topic PRINT --language basic

Context-ID mit Topic-Fallback:
    py chmviewer.py help.chm --topic PRINT --context-id 2101

Direkte interne HTML-Seite:
    py chmviewer.py help.chm --local basic/print.html

Keyword:
    py chmviewer.py help.chm --keyword PRINT


ABWAERTSKOMPATIBEL ZUM BISHERIGEN VIEWER
-----------------------------------------
Der bisherige Parameter --word bleibt erhalten:

    py chmviewer.py help.chm --word PRINT


LEGACY-/HH.EXE-ARTIGE AUFRUFE
-----------------------------
Direktes Thema:
    py chmviewer.py "help.chm::/basic/print.html"

Context-ID:
    py chmviewer.py -mapid 2101 help.chm

Keyword:
    py chmviewer.py -keyword PRINT help.chm

Zusaetzlich werden Slash-Varianten akzeptiert:

    py chmviewer.py /context 2101 help.chm
    py chmviewer.py /topic basic/print.html help.chm
    py chmviewer.py /keyword PRINT help.chm


HTML-HELP-BRIDGE-FORMAT
-----------------------
Fuer eigene Wrapper/Adapter:

    py chmviewer.py help.chm --hh-command HH_HELP_CONTEXT --hh-data 2101

    py chmviewer.py help.chm --hh-command HH_DISPLAY_TOPIC        --hh-data basic/print.html

    py chmviewer.py help.chm --hh-command HH_KEYWORD_LOOKUP        --hh-data PRINT


DELPHI
------
Unter delphi/ liegt:

    ChmViewerCompat.pas

Das Unit stellt bereit:

    ChmViewerTopic(...)
    ChmViewerContext(...)
    ChmViewerKeyword(...)
    ChmViewerHtmlHelp(...)

Damit kann Delphi-Quelltext weiterhin mit den bekannten Semantiken
HH_DISPLAY_TOPIC, HH_HELP_CONTEXT und HH_KEYWORD_LOOKUP arbeiten.

WICHTIG:
Das ist ein Source-Level-Kompatibilitaetsadapter. Eine bereits kompilierte
Fremdanwendung, die direkt hhctrl.ocx/HtmlHelp() aufruft, wird dadurch nicht
automatisch auf chmviewer.exe umgebogen. Dafuer waere ein separater nativer
DLL-/API-Proxy notwendig.


THEME UND UI-ZUSTAND
--------------------
- Dark Mode gilt fuer die gesamte QApplication.
- Fenstergeometrie wird gespeichert.
- Fensterzustand wird gespeichert.
- Splitterposition wird gespeichert.
- Zustand wird vor dem ersten show() wiederhergestellt.


METAINFORMATIONEN
-----------------
helpmeta.example.json zeigt ein empfohlenes Format fuer deine Anwendung:

    Topic-String: "PRINT"
    Sprache:      "basic"
    Context-ID:   2101
    Local:        "basic/print.html"

Empfohlene Prioritaet:
    Local -> Context-ID mit Topic-Fallback -> Keyword -> Topic


ABHAENGIGKEITEN
---------------
    py -m pip install -r requirements.txt


WEBENGINE / REMOTE-URLS / SVG
-----------------------------
Die rechte Hilfeseite darf jetzt Remote-Ressourcen laden:

    QWebEngineSettings.LocalContentCanAccessRemoteUrls = True

Beispiel für eine serverseitig erzeugte SVG-Grafik:

    <img src="http://127.0.0.1:8080/api/ic.php?id=74ls00&rotation=90"
         alt="74LS00">

Der Server sollte für SVG liefern:

    Content-Type: image/svg+xml; charset=utf-8

Bei <img src="..."> ist normalerweise kein JavaScript-CORS-Zugriff nötig.

Für JavaScript/fetch():

    fetch("http://127.0.0.1:8080/api/ic.php?id=74ls00")
      .then(r => r.text())
      .then(svg => document.getElementById("target").innerHTML = svg);

muss der Server CORS erlauben, z.B.:

    Access-Control-Allow-Origin: *

HTTP- und HTTPS-Navigation bleibt nun innerhalb der rechten QWebEngineView.
mailto:-Links werden weiterhin im Standard-Mailprogramm geöffnet.


SHOW SOURCE
-----------
Das Kontextmenü der rechten WebPage enthält eine eigene Aktion:

    Show Source

Die native QtWebEngine-View-Source-Aktion wird ersetzt. Der aktuelle HTML-
Quelltext wird als UTF-8-Datei mit der Endung ".html.txt" in das temporäre
Verzeichnis geschrieben und anschließend mit dem im Betriebssystem für
Textdateien registrierten Standard-Editor geöffnet.

Auch Bearbeiten -> Seiten-Quelltext bzw. Ctrl+U verwendet dieselbe Funktion.


SCROLLBARS IM DARK MODE
-----------------------
Die Scrollbars des linken Themen-/Indexbereichs und der rechten WebEngine
verwenden nun dieselben Grundwerte:

    Breite/Höhe:   16 px
    Track:         #163b73
    Handle:        #245a9a
    Hover:         #3375bd
    Button:        #1d4d87
    Border:        #4b79ad
    Mindest-Handle 24 px

Links werden die Werte über Qt-QSS gesetzt, rechts über WebKit/Chromium-CSS.


CHM Viewer – Topic-Pfeile + eigene Titelleiste
=================================================

Basis:
- chmviewer.py mit Python-generierten Web-Scrollbar-Pfeilen

Neu:
1. Themen/Topic-Scrollbars:
   - Native Qt-Scrollbars der Themen-, Schlüsselwort- und Favoriten-Bäume
     erhalten gelbe Pfeile (#ffd84a), direkt durch Python/QPainter.
   - Die Web-Topic-Seite erhält zusätzlich Python-injizierte Pfeilbuttons
     oben/unten bzw. links/rechts als Fallback für QtWebEngine-Versionen,
     die ::-webkit-scrollbar-button nicht sichtbar rendern.

2. Eigene Titelleiste:
   - Hauptfenster ist Qt.FramelessWindowHint.
   - Titelleiste wird vollständig mit QPainter gezeichnet.
   - Dark Mode: Verlauf von Schwarz über Dunkelgrau nach Grau.
   - Buttons: Minimieren, Maximieren/Wiederherstellen, Schließen.
   - Buttons/Icons werden in Python gezeichnet.
   - Doppelklick auf Titelleiste maximiert/wiederherstellt.
   - Ziehen an der Titelleiste verschiebt das Fenster.

3. Fensterrahmen:
   - sichtbarer 3-Pixel-Rahmen
   - 8 transparente Resize-Griffe:
     links, rechts, oben, unten und vier Ecken
   - passende Resize-Mauszeiger
   - Größenänderung respektiert minimumWidth/minimumHeight
   - Resize-Griffe verschwinden im maximierten Zustand

Prüfung:
- Python-Syntaxprüfung via py_compile: OK

Hinweis:
- Die Web-Topic-Pfeile werden aus Python per JavaScript in die geladene
  HTML-Seite eingesetzt, weil Chromium/QtWebEngine die CSS-Pseudoelemente
  für Scrollbar-Buttons je nach Version nicht zuverlässig anzeigt.

IC SVG Bibliothek – flexible externe Bauteilliste

Dateien:
- ic-svg-library.html: komplette Oberfläche
- data/components.js: empfohlene externe Bauteildaten für CHM/HelpNDoc
- data/components.json: JSON-Spiegeldatei für PHP/APIs

Webserver-Struktur:
/data/components.js
/data/components.json
/b0/74LS00.svg ...
/b90/74LS00.svg ...
/b180/74LS00.svg ...
/b270/74LS00.svg ...

Neue Bauteile werden nur in components.js ergänzt.
Unterstützte Felder: id, name, description, category, family, type, gates, 

inputs, package, file, rotations.

Die HTML-Seite lädt components.js über:
[::CustomServer::]/data/components.js

Warum JS statt fetch(JSON): Ein normales externes Script ist für lokal 
entpackte CHM-Seiten robuster und vermeidet typische CORS-Probleme von 
fetch/XHR.
