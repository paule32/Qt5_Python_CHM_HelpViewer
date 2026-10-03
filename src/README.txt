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
