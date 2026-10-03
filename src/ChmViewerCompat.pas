unit ChmViewerCompat;

{
  Kleiner Delphi/VCL-Adapter fuer den externen CHM Viewer.

  Ziel:
    - Neue Anwendungen koennen weiterhin ihr eigenes --topic-Format nutzen.
    - Aeltere Delphi-Projekte koennen Context-ID, Topic oder Keyword mit
      einer HTML-Help-aehnlichen Semantik an den Viewer weiterreichen.

  Hinweis:
    Dieses Unit ersetzt NICHT hhctrl.ocx und hookt keine bereits kompilierte
    HtmlHelp()-Funktion. Es ist ein Source-Level-Adapter fuer Anwendungen,
    die neu kompiliert werden koennen.
}

interface

uses
  Windows, ShellAPI, SysUtils;

const
  HH_DISPLAY_TOPIC  = $0000;
  HH_KEYWORD_LOOKUP = $000D;
  HH_HELP_CONTEXT   = $000F;

function ChmViewerTopic(
  const ViewerExe, ChmFile, Topic: string
): Boolean;

function ChmViewerContext(
  const ViewerExe, ChmFile: string;
  ContextId: Cardinal
): Boolean;

function ChmViewerKeyword(
  const ViewerExe, ChmFile, Keyword: string
): Boolean;

function ChmViewerHtmlHelp(
  const ViewerExe, ChmFile: string;
  Command: Cardinal;
  const TextData: string;
  NumericData: Cardinal
): Boolean;

implementation

function QuoteArg(const S: string): string;
begin
  Result := '"' + StringReplace(S, '"', '\"', [rfReplaceAll]) + '"';
end;

function RunViewer(
  const ViewerExe, Params: string
): Boolean;
var
  R: HINST;
begin
  R := ShellExecute(
    0,
    'open',
    PChar(ViewerExe),
    PChar(Params),
    nil,
    SW_SHOWNORMAL
  );
  Result := NativeUInt(R) > 32;
end;

function ChmViewerTopic(
  const ViewerExe, ChmFile, Topic: string
): Boolean;
var
  Params: string;
begin
  { Direkte Legacy-Schreibweise wie beim klassischen CHM-Aufruf. }
  Params := QuoteArg(ChmFile + '::/' + Topic);
  Result := RunViewer(ViewerExe, Params);
end;

function ChmViewerContext(
  const ViewerExe, ChmFile: string;
  ContextId: Cardinal
): Boolean;
var
  Params: string;
begin
  { -mapid wird vom Viewer als Legacy-Alias fuer --context-id verstanden. }
  Params :=
    '-mapid ' + IntToStr(ContextId) + ' ' +
    QuoteArg(ChmFile);
  Result := RunViewer(ViewerExe, Params);
end;

function ChmViewerKeyword(
  const ViewerExe, ChmFile, Keyword: string
): Boolean;
var
  Params: string;
begin
  Params :=
    '-keyword ' + QuoteArg(Keyword) + ' ' +
    QuoteArg(ChmFile);
  Result := RunViewer(ViewerExe, Params);
end;

function ChmViewerHtmlHelp(
  const ViewerExe, ChmFile: string;
  Command: Cardinal;
  const TextData: string;
  NumericData: Cardinal
): Boolean;
begin
  case Command of
    HH_DISPLAY_TOPIC:
      Result := ChmViewerTopic(
        ViewerExe,
        ChmFile,
        TextData
      );

    HH_HELP_CONTEXT:
      Result := ChmViewerContext(
        ViewerExe,
        ChmFile,
        NumericData
      );

    HH_KEYWORD_LOOKUP:
      Result := ChmViewerKeyword(
        ViewerExe,
        ChmFile,
        TextData
      );

  else
    Result := False;
  end;
end;

end.
