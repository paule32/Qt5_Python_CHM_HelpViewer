# ---------------------------------------------------------------------------
# Standalone CHM Viewer
# Based on the uploaded chmviewer.py structure.
# PyQt5 + QtWebEngine, Windows CHM extraction, Topics/Keywords/Favorites.
# ---------------------------------------------------------------------------
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import ssl
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, unquote, urlparse

try:
    from PyQt5.QtCore import (
        QPointF,
        QRect,
        QEvent,
        QSettings,
        QSize,
        QTemporaryDir,
        QTimer,
        Qt,
        QUrl,
        pyqtSignal,
    )
    from PyQt5.QtGui import (
        QColor,
        QDesktopServices,
        QFont,
        QLinearGradient,
        QIcon,
        QKeySequence,
        QPainter,
        QPainterPath,
        QPalette,
        QPen,
        QPixmap,
        QTextCursor,
    )
    from PyQt5.QtWidgets import (
        QAbstractButton,
        QAbstractSlider,
        QAction,
        QApplication,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenuBar,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QScrollBar,
        QSizePolicy,
        QSplitter,
        QStatusBar,
        QStyle,
        QTabWidget,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QTreeWidgetItemIterator,
        QVBoxLayout,
        QWidget,
    )
    from PyQt5.QtWebEngineWidgets import (
        QWebEnginePage,
        QWebEngineSettings,
        QWebEngineView,
    )
except ImportError as exc:
    raise SystemExit(
        "PyQt5 / PyQtWebEngine fehlt. Installiere:\n"
        "    py -m pip install PyQt5 PyQtWebEngine\n\n"
        f"Technischer Fehler: {exc}"
    )


APP_ORG = "paule32"
APP_NAME = "CHM Viewer"
CHM_ROLE_LOCAL = Qt.UserRole + 1
CHM_ROLE_TITLE = Qt.UserRole + 2


@dataclass
class ChmSitemapEntry:
    title: str
    local: str = ""
    children: List["ChmSitemapEntry"] = field(default_factory=list)


class ChmSitemapParser(HTMLParser):
    """Parser fuer klassische .hhc/.hhk HTML-Help-Sitemaps."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root: List[ChmSitemapEntry] = []
        self.stack: List[List[ChmSitemapEntry]] = [self.root]
        self.in_object = False
        self.object_type = ""
        self.params: Dict[str, str] = {}
        self.last_entry: Optional[ChmSitemapEntry] = None
        self.seen_initial_ul = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.casefold()
        values = {str(k).casefold(): str(v or "") for k, v in attrs}

        if tag == "object":
            self.in_object = True
            self.object_type = values.get("type", "").casefold()
            self.params = {}
            return

        if tag == "param" and self.in_object:
            name = values.get("name", "").strip().casefold()
            value = values.get("value", "")
            if name:
                self.params[name] = value
            return

        if tag == "ul":
            if not self.seen_initial_ul:
                self.seen_initial_ul = True
                return
            if self.last_entry is not None:
                self.stack.append(self.last_entry.children)
                self.last_entry = None
            return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "object" and self.in_object:
            self.in_object = False
            if "text/sitemap" in self.object_type or not self.object_type:
                title = (
                    self.params.get("name")
                    or self.params.get("keyword")
                    or self.params.get("local")
                    or "(ohne Titel)"
                ).strip()
                local = self.params.get("local", "").strip()
                entry = ChmSitemapEntry(title=title, local=local)
                self.stack[-1].append(entry)
                self.last_entry = entry
            self.params = {}
            self.object_type = ""
            return

        if tag == "ul" and len(self.stack) > 1:
            self.stack.pop()
            self.last_entry = None


def _read_text_guess(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1", errors="replace")


def parse_chm_sitemap(path: Optional[Path]) -> List[ChmSitemapEntry]:
    if path is None or not path.is_file():
        return []
    parser = ChmSitemapParser()
    try:
        parser.feed(_read_text_guess(path))
        parser.close()
    except Exception:
        return []
    return parser.root


def _parse_hhp_sections(path: Optional[Path]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    if path is None or not path.is_file():
        return result
    current = ""
    for raw in _read_text_guess(path).splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().casefold()
            result.setdefault(current, [])
            continue
        if current:
            result.setdefault(current, []).append(raw.rstrip())
    return result


def read_chm_project_options(path: Optional[Path]) -> Dict[str, str]:
    sections = _parse_hhp_sections(path)
    result: Dict[str, str] = {}
    for raw in sections.get("options", []):
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        result[key.strip().casefold()] = value.strip().strip('"')
    return result


def iter_chm_files(root: Path) -> Iterable[Path]:
    try:
        yield from root.rglob("*")
    except OSError:
        return


def find_chm_file_by_suffix(root: Path, suffix: str) -> Optional[Path]:
    suffix = suffix.casefold()
    candidates = [
        p for p in iter_chm_files(root)
        if p.is_file() and p.suffix.casefold() == suffix
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (len(p.relative_to(root).parts), str(p).casefold()))


def clean_chm_local(value: str) -> Tuple[str, str]:
    value = html.unescape(str(value or "")).strip().strip('"').replace("\\", "/")
    if not value:
        return "", ""

    lowered = value.casefold()
    for prefix in ("mk:@msitstore:", "ms-its:", "its:"):
        if lowered.startswith(prefix):
            value = value[len(prefix):]
            lowered = value.casefold()
            break

    if "::/" in value:
        value = value.split("::/", 1)[1]
    elif "::" in value:
        value = value.split("::", 1)[1].lstrip("/")

    if value.casefold().startswith(("http://", "https://", "mailto:", "javascript:")):
        return "", ""

    fragment = ""
    if "#" in value:
        value, fragment = value.split("#", 1)

    value = unquote(value.split("?", 1)[0]).strip().lstrip("/")
    value = re.sub(r"^\./+", "", value)
    parts = [part for part in value.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return "", ""
    return "/".join(parts), fragment


def resolve_chm_path(root: Optional[Path], relative: str) -> Optional[Path]:
    if root is None:
        return None
    relative, _fragment = clean_chm_local(relative)
    if not relative:
        return None

    direct = root.joinpath(*relative.split("/"))
    try:
        resolved = direct.resolve()
        resolved.relative_to(root.resolve())
        if resolved.is_file():
            return resolved
    except (OSError, ValueError):
        pass

    # Case-insensitive fallback; useful for CHMs with inconsistent link casing.
    current = root
    for wanted in relative.split("/"):
        try:
            match = next((p for p in current.iterdir() if p.name.casefold() == wanted.casefold()), None)
        except OSError:
            return None
        if match is None:
            return None
        current = match
    try:
        resolved = current.resolve()
        resolved.relative_to(root.resolve())
        return resolved if resolved.is_file() else None
    except (OSError, ValueError):
        return None


def read_chm_context_map(root: Path) -> Dict[int, str]:
    project = find_chm_file_by_suffix(root, ".hhp")
    sections = _parse_hhp_sections(project)
    symbols: Dict[str, int] = {}
    aliases: Dict[str, str] = {}

    define_re = re.compile(r"^\s*#\s*define\s+([A-Za-z_]\w*)\s+([0-9]+|0x[0-9A-Fa-f]+)")

    sources: List[str] = list(sections.get("map", []))
    # Some CHM projects keep map constants in header files.
    for header in root.rglob("*.h"):
        try:
            sources.extend(_read_text_guess(header).splitlines())
        except OSError:
            pass

    for raw in sources:
        m = define_re.match(raw)
        if m:
            try:
                symbols[m.group(1)] = int(m.group(2), 0)
            except ValueError:
                pass
        elif "=" in raw:
            left, right = raw.split("=", 1)
            left = left.strip()
            right = right.strip()
            try:
                symbols[left] = int(right, 0)
            except ValueError:
                pass

    for raw in sections.get("alias", []):
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        aliases[key.strip()] = value.strip().strip('"')

    result: Dict[int, str] = {}
    for key, local in aliases.items():
        context_id: Optional[int] = symbols.get(key)
        if context_id is None:
            try:
                context_id = int(key, 0)
            except ValueError:
                continue
        if local:
            result[context_id] = local
    return result


class ChmExtractor:
    """Entpackt CHM auf Windows mit hh.exe; 7-Zip dient als Fallback."""

    @staticmethod
    def _hh_candidates() -> List[Path]:
        values: List[Path] = []
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        if windir:
            values.append(Path(windir) / "hh.exe")
            values.append(Path(windir) / "SysWOW64" / "hh.exe")
            values.append(Path(windir) / "System32" / "hh.exe")
        found = shutil.which("hh.exe") or shutil.which("hh")
        if found:
            values.append(Path(found))
        unique: List[Path] = []
        seen = set()
        for path in values:
            key = str(path).casefold()
            if key not in seen and path.is_file():
                unique.append(path)
                seen.add(key)
        return unique

    @staticmethod
    def _has_content(root: Path) -> bool:
        useful = {".htm", ".html", ".hhc", ".hhk", ".hhp"}
        try:
            return any(p.is_file() and p.suffix.casefold() in useful for p in root.rglob("*"))
        except OSError:
            return False

    @classmethod
    def extract(cls, source: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        errors: List[str] = []

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for hh in cls._hh_candidates():
            try:
                subprocess.run(
                    [str(hh), "-decompile", str(destination), str(source)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
                # hh.exe may finish decompilation asynchronously.
                deadline = time.monotonic() + 8.0
                while time.monotonic() < deadline:
                    if cls._has_content(destination):
                        return
                    time.sleep(0.10)
            except OSError as exc:
                errors.append(f"{hh}: {exc}")

        seven_zip = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        if seven_zip:
            try:
                proc = subprocess.run(
                    [seven_zip, "x", "-y", f"-o{destination}", str(source)],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=creationflags,
                )
                if proc.returncode == 0 and any(destination.iterdir()):
                    return
                errors.append(proc.stdout[-1200:] if proc.stdout else "7-Zip konnte CHM nicht entpacken")
            except OSError as exc:
                errors.append(str(exc))

        detail = "\n".join(error for error in errors if error).strip()
        raise RuntimeError(
            "Die CHM-Datei konnte nicht entpackt werden.\n\n"
            "Unter Windows wird zuerst hh.exe -decompile verwendet. "
            "Optional kann 7-Zip als Fallback installiert werden."
            + (f"\n\nDetails:\n{detail}" if detail else "")
        )


class ChmSearchTab(QWidget):
    search_requested = pyqtSignal(str)

    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(placeholder)
        self.search_edit.setClearButtonEnabled(True)

        self.search_button = QPushButton(self)
        self.search_button.setIcon(self._magnifier_icon())
        self.search_button.setIconSize(QSize(18, 18))
        self.search_button.setFixedWidth(36)
        self.search_button.setToolTip("Ersten Treffer suchen")

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.search_edit, 1)
        row.addWidget(self.search_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addLayout(row)
        layout.addWidget(self.tree, 1)

        self.search_edit.returnPressed.connect(self.emit_search)
        self.search_button.clicked.connect(self.emit_search)

    def _magnifier_icon(self) -> QIcon:
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        color = self.palette().color(QPalette.ButtonText)
        painter.setPen(QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawEllipse(4, 3, 10, 10)
        painter.drawLine(13, 12, 19, 18)
        painter.end()
        return QIcon(pixmap)

    def emit_search(self) -> None:
        self.search_requested.emit(self.search_edit.text().strip())


class ChmWebPage(QWebEnginePage):
    def _main_window(self):
        view = self.view()
        return view.window() if view is not None else None

    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:
        scheme = url.scheme().lower()

        if is_main_frame and scheme in ("mk", "ms-its", "its"):
            window = self._main_window()
            if window is not None and hasattr(window, "load_local"):
                window.load_local(url.toString())
            return False

        if (
            is_main_frame
            and navigation_type == QWebEnginePage.NavigationTypeLinkClicked
            and scheme == "mailto"
        ):
            QDesktopServices.openUrl(url)
            return False

        return super().acceptNavigationRequest(url, navigation_type, is_main_frame)

    def certificateError(self, error) -> bool:
        url = error.url()
        host = url.host().casefold()
        window = self._main_window()

        if window is not None and hasattr(window, "is_certificate_host_trusted"):
            if window.is_certificate_host_trusted(host):
                print(
                    "[CHM NETWORK] Zertifikatsfehler für bereits freigegebenen Host "
                    f"{host}: {error.errorDescription()}",
                    flush=True,
                )
                return True

        overridable = True
        try:
            overridable = bool(error.isOverridable())
        except Exception:
            pass

        if not overridable:
            print(
                "[CHM NETWORK] Nicht übersteuerbarer Zertifikatsfehler: "
                f"{url.toString()} :: {error.errorDescription()}",
                flush=True,
            )
            return False

        parent = window if isinstance(window, QWidget) else None
        answer = QMessageBox.warning(
            parent,
            "HTTPS-Zertifikat",
            "Beim Laden einer Remote-Ressource ist ein Zertifikatsfehler "
            "aufgetreten.\n\n"
            f"Host: {host}\n"
            f"URL: {url.toString()}\n\n"
            f"{error.errorDescription()}\n\n"
            "Möchtest du diesem Host trotzdem vertrauen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            if window is not None and hasattr(window, "trust_certificate_host"):
                window.trust_certificate_host(host)
            print(f"[CHM NETWORK] Zertifikat für Host freigegeben: {host}", flush=True)
            return True

        return False

    def javaScriptConsoleMessage(self, level, message, line_number, source_id) -> None:
        print(
            f"[CHM WEB {level}] {source_id}:{line_number}: {message}",
            flush=True,
        )
        try:
            super().javaScriptConsoleMessage(level, message, line_number, source_id)
        except Exception:
            pass


class ChmWebView(QWebEngineView):
    """WebView mit einem funktionierenden 'Show Source'-Kontextmenü."""

    show_source_requested = pyqtSignal()

    def contextMenuEvent(self, event) -> None:
        menu = self.page().createStandardContextMenu()

        # QtWebEngine besitzt selbst eine View-Source-Aktion, deren Verhalten
        # je nach Qt5-Build/Deployment wenig hilfreich sein kann. Wir entfernen
        # sie aus dem Standardmenü und ersetzen sie durch unsere eigene Aktion,
        # die den Quelltext im Standard-Texteditor des Betriebssystems öffnet.
        try:
            if hasattr(QWebEnginePage, "ViewSource"):
                native_source = self.page().action(QWebEnginePage.ViewSource)
                if native_source is not None:
                    menu.removeAction(native_source)
        except Exception:
            pass

        # Falls die native Aktion nicht als identisches QAction-Objekt geliefert
        # wurde, entfernen wir lokalisierte Varianten über den sichtbaren Text.
        for action in list(menu.actions()):
            title = action.text().replace("&", "").strip().casefold()
            if (
                "view source" in title
                or "show source" in title
                or "seitenquelltext" in title
                or "quelltext anzeigen" in title
            ):
                menu.removeAction(action)

        menu.addSeparator()
        source_action = menu.addAction("Show Source")
        source_action.triggered.connect(self.show_source_requested.emit)
        menu.exec_(event.globalPos())


class ChmSourceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seiten-Quelltext")
        self.resize(900, 650)
        self.editor = QPlainTextEdit(self)
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout = QVBoxLayout(self)
        layout.addWidget(self.editor, 1)



class ScrollBarArrowButton(QWidget):
    """Kleiner, von Python gezeichneter Pfeil direkt auf einer QScrollBar."""

    SIZE = 16
    ARROW_COLOR = QColor("#ffd84a")

    def __init__(self, scrollbar: QScrollBar, direction: str):
        super().__init__(scrollbar)
        self.scrollbar = scrollbar
        self.direction = direction

        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.ArrowCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setToolTip({
            "up": "Eine Zeile nach oben",
            "down": "Eine Zeile nach unten",
            "left": "Nach links",
            "right": "Nach rechts",
        }.get(direction, ""))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Passt optisch zu den bestehenden Scrollbars des Viewers.
        if self.underMouse():
            background = QColor("#2867aa")
        else:
            background = QColor("#1d4d87")

        painter.fillRect(self.rect(), background)

        border_pen = QPen(QColor("#4b79ad"), 1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        painter.setPen(Qt.NoPen)
        painter.setBrush(self.ARROW_COLOR)

        cx = self.width() / 2.0
        cy = self.height() / 2.0
        s = 4.0

        path = QPainterPath()

        if self.direction == "up":
            path.moveTo(cx, cy - s)
            path.lineTo(cx + s, cy + s)
            path.lineTo(cx - s, cy + s)

        elif self.direction == "down":
            path.moveTo(cx - s, cy - s)
            path.lineTo(cx + s, cy - s)
            path.lineTo(cx, cy + s)

        elif self.direction == "left":
            path.moveTo(cx - s, cy)
            path.lineTo(cx + s, cy - s)
            path.lineTo(cx + s, cy + s)

        else:  # right
            path.moveTo(cx + s, cy)
            path.lineTo(cx - s, cy - s)
            path.lineTo(cx - s, cy + s)

        path.closeSubpath()
        painter.drawPath(path)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.direction in ("up", "left"):
                self.scrollbar.triggerAction(
                    QAbstractSlider.SliderSingleStepSub
                )
            else:
                self.scrollbar.triggerAction(
                    QAbstractSlider.SliderSingleStepAdd
                )
            event.accept()
            return

        super().mousePressEvent(event)


class ScrollBarArrowController(QWidget):
    """Positioniert Pfeile auf einer bereits vorhandenen Qt-Scrollbar."""

    def __init__(self, scrollbar: QScrollBar):
        super().__init__(scrollbar)
        self.scrollbar = scrollbar
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        if scrollbar.orientation() == Qt.Vertical:
            self.first = ScrollBarArrowButton(scrollbar, "up")
            self.second = ScrollBarArrowButton(scrollbar, "down")
        else:
            self.first = ScrollBarArrowButton(scrollbar, "left")
            self.second = ScrollBarArrowButton(scrollbar, "right")

        # Die Buttons selbst müssen Mausereignisse empfangen können.
        self.first.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.second.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        scrollbar.installEventFilter(self)
        self.reposition()

    def reposition(self):
        sb = self.scrollbar
        size = ScrollBarArrowButton.SIZE

        if sb.orientation() == Qt.Vertical:
            self.first.setGeometry(
                0,
                0,
                sb.width(),
                size,
            )
            self.second.setGeometry(
                0,
                max(0, sb.height() - size),
                sb.width(),
                size,
            )
        else:
            self.first.setGeometry(
                0,
                0,
                size,
                sb.height(),
            )
            self.second.setGeometry(
                max(0, sb.width() - size),
                0,
                size,
                sb.height(),
            )

        self.first.raise_()
        self.second.raise_()

    def eventFilter(self, watched, event):
        if watched is self.scrollbar and event.type() in (
            QEvent.Resize,
            QEvent.Show,
            QEvent.LayoutRequest,
        ):
            QTimer.singleShot(0, self.reposition)

        return False


class TitleBarButton(QAbstractButton):
    """Programmseitig gezeichneter Button der eigenen Titelleiste."""

    def __init__(self, kind: str, title_bar):
        super().__init__(title_bar)
        self.kind = kind
        self.title_bar = title_bar
        self.setFixedSize(46, 30)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        dark = self.title_bar.is_dark_mode()
        hovered = self.underMouse()
        pressed = self.isDown()

        if self.kind == "close" and hovered:
            bg = QColor("#c42b1c" if not pressed else "#a62216")
        elif hovered:
            bg = QColor(255, 255, 255, 34) if dark else QColor(0, 0, 0, 28)
        elif pressed:
            bg = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 20)
        else:
            bg = Qt.transparent

        if bg != Qt.transparent:
            painter.fillRect(self.rect(), bg)

        color = QColor("#ffffff") if dark else QColor("#111111")
        if self.kind == "close" and hovered:
            color = QColor("#ffffff")

        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.SquareCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        if self.kind == "minimize":
            painter.drawLine(int(cx - 6), int(cy + 4), int(cx + 6), int(cy + 4))

        elif self.kind == "restore":
            # Im maximierten Zustand: klassisches Wiederherstellen-Symbol.
            if self.window().isMaximized():
                painter.drawRect(int(cx - 4), int(cy - 6), 9, 8)
                painter.drawRect(int(cx - 7), int(cy - 3), 9, 8)
            else:
                # Im Normalzustand dient derselbe Button als Maximieren.
                painter.drawRect(int(cx - 6), int(cy - 6), 12, 11)

        elif self.kind == "close":
            painter.drawLine(int(cx - 5), int(cy - 5), int(cx + 5), int(cy + 5))
            painter.drawLine(int(cx + 5), int(cy - 5), int(cx - 5), int(cy + 5))

        painter.end()


class CustomTitleBar(QWidget):
    """Eigene Titelleiste: Gradient, Ziehen, Doppelklick und Fensterbuttons."""

    HEIGHT = 32

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._dragging = False
        self._drag_offset = None

        self.setFixedHeight(self.HEIGHT)
        self.setMouseTracking(True)
        self.setObjectName("chm_custom_titlebar")

        self.minimize_button = TitleBarButton("minimize", self)
        self.restore_button = TitleBarButton("restore", self)
        self.close_button = TitleBarButton("close", self)

        self.minimize_button.setToolTip("Minimieren")
        self.restore_button.setToolTip("Maximieren / Wiederherstellen")
        self.close_button.setToolTip("Schließen")

        self.minimize_button.clicked.connect(self._window.showMinimized)
        self.restore_button.clicked.connect(self.toggle_max_restore)
        self.close_button.clicked.connect(self._window.close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 1, 0, 1)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.restore_button)
        layout.addWidget(self.close_button)

    def is_dark_mode(self) -> bool:
        return bool(getattr(self._window, "dark_mode_enabled", True))

    def toggle_max_restore(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.update_state()

    def update_state(self):
        self.restore_button.update()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        gradient = QLinearGradient(0, 0, self.width(), 0)
        if self.is_dark_mode():
            # Gewünschter Dark-Mode-Verlauf: Schwarz -> Grau.
            gradient.setColorAt(0.0, QColor("#050505"))
            gradient.setColorAt(0.48, QColor("#202020"))
            gradient.setColorAt(1.0, QColor("#555555"))
            text_color = QColor("#ffffff")
        else:
            gradient.setColorAt(0.0, QColor("#f5f5f5"))
            gradient.setColorAt(1.0, QColor("#a8a8a8"))
            text_color = QColor("#111111")

        painter.fillRect(self.rect(), gradient)

        painter.setPen(text_color)
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)

        right_limit = self.width() - (
            self.minimize_button.width()
            + self.restore_button.width()
            + self.close_button.width()
            + 12
        )
        text_rect = QRect(12, 0, max(0, right_limit - 12), self.height())
        painter.drawText(
            text_rect,
            Qt.AlignVCenter | Qt.AlignLeft,
            self._window.windowTitle(),
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._window.isMaximized():
            self._dragging = True
            self._drag_offset = event.globalPos() - self._window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._dragging
            and self._drag_offset is not None
            and (event.buttons() & Qt.LeftButton)
            and not self._window.isMaximized()
        ):
            self._window.move(event.globalPos() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_max_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class WindowResizeHandle(QWidget):
    """Transparenter Griff zum Skalieren eines frameless Fensters."""

    def __init__(self, owner, edges: str):
        super().__init__(owner)
        self.owner = owner
        self.edges = edges
        self._press_global = None
        self._start_geometry = None

        cursor = Qt.ArrowCursor
        if edges in ("left", "right"):
            cursor = Qt.SizeHorCursor
        elif edges in ("top", "bottom"):
            cursor = Qt.SizeVerCursor
        elif edges in ("top-left", "bottom-right"):
            cursor = Qt.SizeFDiagCursor
        elif edges in ("top-right", "bottom-left"):
            cursor = Qt.SizeBDiagCursor

        self.setCursor(cursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.owner.isMaximized():
            self._press_global = event.globalPos()
            self._start_geometry = QRect(self.owner.geometry())
            self.grabMouse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_global is None
            or self._start_geometry is None
            or not (event.buttons() & Qt.LeftButton)
            or self.owner.isMaximized()
        ):
            super().mouseMoveEvent(event)
            return

        delta = event.globalPos() - self._press_global
        rect = QRect(self._start_geometry)

        min_w = self.owner.minimumWidth()
        min_h = self.owner.minimumHeight()

        if "left" in self.edges:
            new_left = min(
                rect.left() + delta.x(),
                rect.right() - min_w + 1,
            )
            rect.setLeft(new_left)

        if "right" in self.edges:
            new_right = max(
                rect.right() + delta.x(),
                rect.left() + min_w - 1,
            )
            rect.setRight(new_right)

        if "top" in self.edges:
            new_top = min(
                rect.top() + delta.y(),
                rect.bottom() - min_h + 1,
            )
            rect.setTop(new_top)

        if "bottom" in self.edges:
            new_bottom = max(
                rect.bottom() + delta.y(),
                rect.top() + min_h - 1,
            )
            rect.setBottom(new_bottom)

        self.owner.setGeometry(rect)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._press_global is not None:
            try:
                self.releaseMouse()
            except Exception:
                pass
        self._press_global = None
        self._start_geometry = None
        super().mouseReleaseEvent(event)



class MainWindow(QMainWindow):
    CONTENT_THEME_STYLE_ID = "d64-chm-content-theme"
    WINDOW_BORDER_WIDTH = 3
    RESIZE_HANDLE_SIZE = 7

    remote_asset_ready = pyqtSignal(str, str)
    remote_asset_failed = pyqtSignal(str, str)

    def __init__(self, parent=None, dark_mode: Optional[bool] = None):
        super().__init__(parent)

        # Eigene Titelleiste / eigener 3-px-Rahmen.
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setContentsMargins(
            self.WINDOW_BORDER_WIDTH,
            self.WINDOW_BORDER_WIDTH,
            self.WINDOW_BORDER_WIDTH,
            self.WINDOW_BORDER_WIDTH,
        )

        # Einstellungen stehen bereits vor dem Aufbau der sichtbaren Widgets
        # zur Verfügung. Dadurch können Theme, Fenstergeometrie und Splitter
        # vor dem ersten Anzeigen wiederhergestellt werden.
        self.settings = QSettings(APP_ORG, APP_NAME)

        if dark_mode is None:
            self.dark_mode_enabled = self.settings.value(
                "ui/dark_mode",
                True,
                type=bool,
            )
        else:
            self.dark_mode_enabled = bool(dark_mode)

        self._remember_application_defaults()
        self.apply_application_theme()

        self.setObjectName("chm_viewer_mainwindow")
        self.setWindowTitle("CHM Viewer")
        self.resize(1000, 700)
        self.setMinimumSize(800, 500)

        self.temporary: Optional[tempfile.TemporaryDirectory] = None
        self.content_root: Optional[Path] = None
        self.chm_path: Optional[Path] = None
        self.home_local = ""
        self.source_dialogs: List[ChmSourceDialog] = []
        self.source_temp_files: List[Path] = []
        # Remote-Assets ausschließlich im System-TEMP-Verzeichnis halten.
        # Zusätzlich wird der Cache beim Beenden explizit gelöscht.
        remote_asset_template = str(
            Path(tempfile.gettempdir()) / "chmviewer_remote_assets_XXXXXX"
        )
        self.remote_asset_cache = QTemporaryDir(remote_asset_template)
        self.remote_asset_cache.setAutoRemove(True)

        self.remote_asset_inflight = set()
        self._closing = False
        self.context_id_map: Dict[int, str] = {}
        self.pending_context_language = ""
        self.pending_context_word = ""
        self.pending_context_id = 0
        self.pending_local = ""
        self.pending_keyword = ""

        self.create_actions()
        self.create_menu()
        self.create_custom_titlebar()
        self.create_toolbar()
        self.create_content()
        self.create_statusbar()
        self.connect_signals()
        self.install_native_scrollbar_arrows()
        self.create_resize_handles()
        self.apply_widget_theme()
        self.restore_ui_state()
        self._layout_resize_handles()
        self.update_navigation()

    # ---- UI ---------------------------------------------------------------
    def create_actions(self) -> None:
        style = self.style()
        self.open_action = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Hilfe öffnen …", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.setToolTip("CHM-Datei öffnen")

        self.open_directory_action = QAction("Hilfe-Verzeichnis öffnen …", self)
        self.quit_action = QAction("Programm beenden", self)
        self.quit_action.setShortcut(QKeySequence.Quit)
        self.copy_action = QAction("Kopieren", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        self.source_action = QAction("Seiten-Quelltext", self)
        self.source_action.setShortcut(QKeySequence("Ctrl+U"))
        self.about_action = QAction("Über …", self)
        self.dark_action = QAction("Dark Mode", self, checkable=True)
        self.dark_action.setChecked(self.dark_mode_enabled)

        self.home_action = QAction(style.standardIcon(QStyle.SP_DirHomeIcon), "Start", self)
        self.back_action = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Zurück", self)
        self.forward_action = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Vor", self)

    def create_menu(self) -> None:
        # Eigene QMenuBar, damit sie unter der selbst gezeichneten Titelleiste
        # in einem gemeinsamen QMainWindow-Menü-Widget sitzen kann.
        self.main_menu_bar = QMenuBar(self)
        self.main_menu_bar.setObjectName("chm_main_menu_bar")

        file_menu = self.main_menu_bar.addMenu("Datei")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.open_directory_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        edit_menu = self.main_menu_bar.addMenu("Bearbeiten")
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.source_action)

        view_menu = self.main_menu_bar.addMenu("Ansicht")
        view_menu.addAction(self.dark_action)

        help_menu = self.main_menu_bar.addMenu("Hilfe")
        help_menu.addAction(self.about_action)

    def create_custom_titlebar(self) -> None:
        self.title_bar = CustomTitleBar(self)

        header = QWidget(self)
        header.setObjectName("chm_header_widget")

        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.title_bar)
        layout.addWidget(self.main_menu_bar)

        self.setMenuWidget(header)
        self.windowTitleChanged.connect(lambda _title: self.title_bar.update())

    def install_native_scrollbar_arrows(self) -> None:
        """Gelbe Pfeile ausschließlich in den bestehenden TOC-Scrollbars.

        Keine zusätzlichen Pfeile werden in das HTML-Dokument eingeblendet.
        """
        self._toc_scrollbar_arrow_controllers = []

        # Gewünscht ist ausdrücklich der TOC / Table of Contents links.
        toc_tree = self.topics_tab.tree

        for scrollbar in (
            toc_tree.verticalScrollBar(),
            toc_tree.horizontalScrollBar(),
        ):
            controller = ScrollBarArrowController(scrollbar)
            self._toc_scrollbar_arrow_controllers.append(controller)

            # Nach Layout-/Style-Berechnung nochmals exakt positionieren.
            QTimer.singleShot(0, controller.reposition)


    def create_resize_handles(self) -> None:
        self._resize_handles = {
            "left": WindowResizeHandle(self, "left"),
            "right": WindowResizeHandle(self, "right"),
            "top": WindowResizeHandle(self, "top"),
            "bottom": WindowResizeHandle(self, "bottom"),
            "top-left": WindowResizeHandle(self, "top-left"),
            "top-right": WindowResizeHandle(self, "top-right"),
            "bottom-left": WindowResizeHandle(self, "bottom-left"),
            "bottom-right": WindowResizeHandle(self, "bottom-right"),
        }
        self._layout_resize_handles()

    def _layout_resize_handles(self) -> None:
        handles = getattr(self, "_resize_handles", None)
        if not handles:
            return

        if self.isMaximized() or self.isFullScreen():
            for handle in handles.values():
                handle.hide()
            return

        for handle in handles.values():
            handle.show()

        w = self.width()
        h = self.height()
        s = self.RESIZE_HANDLE_SIZE

        handles["top-left"].setGeometry(0, 0, s, s)
        handles["top-right"].setGeometry(max(0, w - s), 0, s, s)
        handles["bottom-left"].setGeometry(0, max(0, h - s), s, s)
        handles["bottom-right"].setGeometry(
            max(0, w - s),
            max(0, h - s),
            s,
            s,
        )

        handles["top"].setGeometry(s, 0, max(0, w - 2 * s), s)
        handles["bottom"].setGeometry(
            s,
            max(0, h - s),
            max(0, w - 2 * s),
            s,
        )
        handles["left"].setGeometry(0, s, s, max(0, h - 2 * s))
        handles["right"].setGeometry(
            max(0, w - s),
            s,
            s,
            max(0, h - 2 * s),
        )

        for handle in handles.values():
            handle.raise_()

    def window_border_color(self) -> QColor:
        if self.dark_mode_enabled:
            return QColor("#707070")
        return QColor("#707070")

    def create_toolbar(self) -> None:
        self.navigation_toolbar = QToolBar("Navigation", self)
        self.navigation_toolbar.setObjectName("chm_navigation_toolbar")
        self.navigation_toolbar.setMovable(False)
        self.navigation_toolbar.setIconSize(QSize(20, 20))
        self.navigation_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.navigation_toolbar.addAction(self.open_action)
        self.navigation_toolbar.addSeparator()
        self.navigation_toolbar.addAction(self.home_action)
        self.navigation_toolbar.addAction(self.back_action)
        self.navigation_toolbar.addAction(self.forward_action)
        self.addToolBar(Qt.TopToolBarArea, self.navigation_toolbar)

    def create_content(self) -> None:
        self.tabs = QTabWidget(self)
        self.topics_tab = ChmSearchTab("Thema/Topic suchen …", self.tabs)
        self.keywords_tab = ChmSearchTab("Schlüsselwort suchen …", self.tabs)
        self.favorites_tab = ChmSearchTab("Favorit suchen …", self.tabs)
        self.tabs.addTab(self.topics_tab, "Themen")
        self.tabs.addTab(self.keywords_tab, "Schlüsselwörter")
        self.tabs.addTab(self.favorites_tab, "Favoriten")

        favorites_row = QHBoxLayout()
        self.add_favorite_button = QPushButton("Aktuelle Seite hinzufügen", self.favorites_tab)
        self.remove_favorite_button = QPushButton("Entfernen", self.favorites_tab)
        favorites_row.addWidget(self.add_favorite_button)
        favorites_row.addWidget(self.remove_favorite_button)
        favorites_row.addStretch(1)
        self.favorites_tab.layout().addLayout(favorites_row)

        self.web_view = ChmWebView(self)
        self.web_view.setObjectName("chm_content_view")
        self.web_page = ChmWebPage(self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_page.setBackgroundColor(self.content_background_color())

        web_settings = self.web_page.settings()
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessFileUrls,
            True,
        )
        # Gewollt: lokale, aus CHM entpackte HTML-Seiten dürfen HTTP/HTTPS-
        # Ressourcen laden. Damit funktionieren z.B.
        # <img src="http://server/api/ic.php?..."> sowie Ajax/fetch-Aufrufe
        # (bei fetch/XHR muss der Server zusätzlich passende CORS-Header senden).
        web_settings.setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls,
            True,
        )
        web_settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        web_settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        try:
            web_settings.setAttribute(
                QWebEngineSettings.AllowRunningInsecureContent,
                True,
            )
        except (AttributeError, TypeError):
            pass

        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self.web_view)
        self.splitter.setSizes([360, 820])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # QMainWindow braucht ein echtes CentralWidget; kein Layout direkt auf QMainWindow.
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

        self.show_empty_page()

    def create_statusbar(self) -> None:
        self.status_bar = QStatusBar(self)
        self.file_status = QLabel("Keine CHM-Datei geöffnet", self)
        self.file_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status_bar.addPermanentWidget(self.file_status, 1)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit", 3000)

    def connect_signals(self) -> None:
        self.open_action.triggered.connect(self.choose_chm)
        self.open_directory_action.triggered.connect(self.choose_help_directory)
        self.quit_action.triggered.connect(self.close)
        self.copy_action.triggered.connect(lambda: self.web_page.triggerAction(QWebEnginePage.Copy))
        self.source_action.triggered.connect(self.show_page_source)
        self.web_view.show_source_requested.connect(self.show_page_source)
        self.about_action.triggered.connect(self.show_about)
        self.dark_action.toggled.connect(self.set_dark_mode)
        self.home_action.triggered.connect(self.go_home)
        self.back_action.triggered.connect(self.web_view.back)
        self.forward_action.triggered.connect(self.web_view.forward)

        self.topics_tab.search_requested.connect(lambda text: self.find_first(self.topics_tab.tree, text))
        self.keywords_tab.search_requested.connect(lambda text: self.find_first(self.keywords_tab.tree, text))
        self.favorites_tab.search_requested.connect(lambda text: self.find_first(self.favorites_tab.tree, text))

        self.topics_tab.tree.currentItemChanged.connect(self.tree_item_changed)
        self.keywords_tab.tree.currentItemChanged.connect(self.tree_item_changed)
        self.favorites_tab.tree.currentItemChanged.connect(self.tree_item_changed)
        self.favorites_tab.tree.currentItemChanged.connect(lambda *_: self.update_navigation())

        self.add_favorite_button.clicked.connect(self.add_current_favorite)
        self.remove_favorite_button.clicked.connect(self.remove_current_favorite)

        self.web_view.loadStarted.connect(lambda: self.status_bar.showMessage("Lade Seite …"))
        self.web_view.loadProgress.connect(lambda value: self.status_bar.showMessage(f"Lade Seite … {value} %"))
        self.web_view.loadFinished.connect(self.load_finished)
        self.web_view.urlChanged.connect(lambda _url: self.update_navigation())
        self.remote_asset_ready.connect(self._apply_resolved_remote_asset)
        self.remote_asset_failed.connect(self._report_remote_asset_failure)
        self.web_view.titleChanged.connect(self.title_changed)

    # ---- Theme ------------------------------------------------------------
    def _remember_application_defaults(self) -> None:
        """Merkt die ursprüngliche Qt-Palette und das globale Stylesheet."""
        app = QApplication.instance()
        if app is None:
            return

        if not hasattr(app, "_chm_default_palette"):
            app._chm_default_palette = QPalette(app.palette())
        if not hasattr(app, "_chm_default_stylesheet"):
            app._chm_default_stylesheet = app.styleSheet()

    def application_dark_palette(self) -> QPalette:
        """Dunkle Palette für die komplette Qt-Anwendung."""
        palette = QPalette()

        window = QColor("#202124")
        base = QColor("#15171a")
        alternate = QColor("#25282d")
        text = QColor("#f1f3f4")
        disabled_text = QColor("#7d828a")
        button = QColor("#2b2f34")
        highlight = QColor("#2f6f9f")
        highlighted_text = QColor("#ffffff")
        link = QColor("#66b3ff")

        palette.setColor(QPalette.Window, window)
        palette.setColor(QPalette.WindowText, text)
        palette.setColor(QPalette.Base, base)
        palette.setColor(QPalette.AlternateBase, alternate)
        palette.setColor(QPalette.ToolTipBase, QColor("#30343a"))
        palette.setColor(QPalette.ToolTipText, text)
        palette.setColor(QPalette.Text, text)
        palette.setColor(QPalette.Button, button)
        palette.setColor(QPalette.ButtonText, text)
        palette.setColor(QPalette.BrightText, QColor("#ff6666"))
        palette.setColor(QPalette.Link, link)
        palette.setColor(QPalette.Highlight, highlight)
        palette.setColor(QPalette.HighlightedText, highlighted_text)

        for group in (QPalette.Disabled, QPalette.Inactive):
            palette.setColor(group, QPalette.WindowText, disabled_text)
            palette.setColor(group, QPalette.Text, disabled_text)
            palette.setColor(group, QPalette.ButtonText, disabled_text)

        # PlaceholderText gibt es in den verwendeten Qt5-Versionen.
        try:
            palette.setColor(QPalette.PlaceholderText, QColor("#9aa0a6"))
        except AttributeError:
            pass

        return palette

    def application_dark_stylesheet(self) -> str:
        """Zusatz-QSS für Bereiche, die nur per Palette uneinheitlich wirken."""
        return """
QMainWindow, QDialog, QWidget {
    background-color: #202124;
    color: #f1f3f4;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background-color: #25282d;
    color: #f1f3f4;
}
QWidget#chm_header_widget {
    background: transparent;
}
QWidget#chm_custom_titlebar {
    background: transparent;
}
QMenuBar::item:selected, QMenu::item:selected {
    background-color: #365f7d;
}
QLineEdit, QPlainTextEdit, QTextEdit, QTreeWidget, QTreeView,
QListWidget, QListView, QTableWidget, QTableView, QComboBox,
QSpinBox, QDoubleSpinBox {
    background-color: #15171a;
    color: #f1f3f4;
    border: 1px solid #4a4f57;
    selection-background-color: #2f6f9f;
    selection-color: #ffffff;
}
QPushButton, QToolButton {
    background-color: #2b2f34;
    color: #f1f3f4;
    border: 1px solid #555b64;
    border-radius: 3px;
    padding: 4px 8px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #353a40;
}
QPushButton:pressed, QToolButton:pressed {
    background-color: #181a1d;
}
QPushButton:disabled, QToolButton:disabled {
    color: #7d828a;
}
QTabWidget::pane {
    border: 1px solid #4a4f57;
}
QTabBar::tab {
    background-color: #2b2f34;
    color: #dfe3e7;
    padding: 6px 10px;
    border: 1px solid #4a4f57;
}
QTabBar::tab:selected {
    background-color: #3a3f46;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #2b2f34;
    color: #f1f3f4;
    border: 1px solid #4a4f57;
}
QSplitter::handle {
    background-color: #454a51;
}
QToolTip {
    background-color: #30343a;
    color: #ffffff;
    border: 1px solid #666b73;
}

/* Einheitliche Dark-Mode-Scrollbars für Themenbaum und alle Qt-Widgets. */
QScrollBar:vertical {
    background: #163b73;
    width: 16px;
    margin: 16px 0 16px 0;
    border: 1px solid #4b79ad;
}
QScrollBar::handle:vertical {
    background: #245a9a;
    min-height: 24px;
    border: 1px solid #4b79ad;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #3375bd;
}
QScrollBar::sub-line:vertical,
QScrollBar::add-line:vertical {
    background: #1d4d87;
    height: 16px;
    border: 1px solid #4b79ad;
}
QScrollBar::sub-line:vertical {
    subcontrol-position: top;
    subcontrol-origin: margin;
}
QScrollBar::add-line:vertical {
    subcontrol-position: bottom;
    subcontrol-origin: margin;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: #163b73;
}

QScrollBar:horizontal {
    background: #163b73;
    height: 16px;
    margin: 0 16px 0 16px;
    border: 1px solid #4b79ad;
}
QScrollBar::handle:horizontal {
    background: #245a9a;
    min-width: 24px;
    border: 1px solid #4b79ad;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #3375bd;
}
QScrollBar::sub-line:horizontal,
QScrollBar::add-line:horizontal {
    background: #1d4d87;
    width: 16px;
    border: 1px solid #4b79ad;
}
QScrollBar::sub-line:horizontal {
    subcontrol-position: left;
    subcontrol-origin: margin;
}
QScrollBar::add-line:horizontal {
    subcontrol-position: right;
    subcontrol-origin: margin;
}
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: #163b73;
}
"""

    def apply_application_theme(self) -> None:
        """Wendet Light/Dark auf die komplette QApplication an."""
        app = QApplication.instance()
        if app is None:
            return

        self._remember_application_defaults()

        if self.dark_mode_enabled:
            app.setPalette(self.application_dark_palette())
            app.setStyleSheet(self.application_dark_stylesheet())
        else:
            default_palette = getattr(app, "_chm_default_palette", None)
            default_stylesheet = getattr(app, "_chm_default_stylesheet", "")
            if default_palette is not None:
                app.setPalette(QPalette(default_palette))
            app.setStyleSheet(default_stylesheet)

    def content_background_color(self) -> QColor:
        return QColor("#000000" if self.dark_mode_enabled else "#ffffff")

    def content_foreground_color(self) -> QColor:
        return QColor("#ffffff" if self.dark_mode_enabled else "#000000")

    def scrollbar_arrow_data_uri(self, direction: str, color: str = "#ffd84a") -> str:
        """Erzeugt die Scrollbar-Pfeilgrafik vollständig in Python.

        Die zurückgegebene SVG wird als Data-URI in das von Python injizierte
        QWebEngine-CSS eingesetzt. Die CHM-/HTML-Datei selbst braucht damit
        keinerlei Scrollbar-Pfeildefinitionen.
        """
        paths = {
            "up": "M 8 3 L 14 11 H 2 Z",
            "down": "M 2 5 H 14 L 8 13 Z",
            "left": "M 3 8 L 11 2 V 14 Z",
            "right": "M 13 8 L 5 2 V 14 Z",
        }

        path = paths.get(str(direction).casefold())
        if path is None:
            raise ValueError(f"Unbekannte Scrollbar-Pfeilrichtung: {direction}")

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="16" height="16" viewBox="0 0 16 16">'
            f'<path fill="{color}" d="{path}"/>'
            '</svg>'
        )
        return "data:image/svg+xml," + quote(svg, safe="")

    def content_theme_css(self) -> str:
        # Die Pfeile werden ausschließlich hier in Python erzeugt.
        # HelpNDoc-/CHM-Seiten müssen keine Pfeilgrafiken definieren.
        arrow_color = "#ffd84a"
        arrow_up = self.scrollbar_arrow_data_uri("up", arrow_color)
        arrow_down = self.scrollbar_arrow_data_uri("down", arrow_color)
        arrow_left = self.scrollbar_arrow_data_uri("left", arrow_color)
        arrow_right = self.scrollbar_arrow_data_uri("right", arrow_color)

        if self.dark_mode_enabled:
            background, foreground = "#000000", "#ffffff"
            link, visited, active = "#66b3ff", "#c792ea", "#ffcc66"
            scheme = "dark"
            scroll_track = "#163b73"
            scroll_thumb = "#245a9a"
            scroll_thumb_hover = "#3375bd"
            scroll_button = "#1d4d87"
            scroll_button_hover = "#2867aa"
            scroll_border = "#4b79ad"
        else:
            background, foreground = "#ffffff", "#000000"
            link, visited, active = "#0000ee", "#551a8b", "#ee0000"
            scheme = "light"
            scroll_track = "#e7e7e7"
            scroll_thumb = "#b7b7b7"
            scroll_thumb_hover = "#969696"
            scroll_button = "#4a4a4a"
            scroll_button_hover = "#606060"
            scroll_border = "#777777"

        scrollbar_css = f"""
::-webkit-scrollbar {{
    width: 16px !important;
    height: 16px !important;
    background: {scroll_track} !important;
}}
::-webkit-scrollbar-track {{
    background: {scroll_track} !important;
    border: 1px solid {scroll_border} !important;
}}
::-webkit-scrollbar-thumb {{
    background: {scroll_thumb} !important;
    border: 1px solid {scroll_border} !important;
    border-radius: 3px !important;
    min-height: 24px;
    min-width: 24px;
}}
::-webkit-scrollbar-thumb:hover {{
    background: {scroll_thumb_hover} !important;
}}
::-webkit-scrollbar-button:single-button {{
    width: 16px !important;
    height: 16px !important;
    display: block !important;
    background-color: {scroll_button} !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
    background-size: 12px 12px !important;
    border: 1px solid {scroll_border} !important;
}}
::-webkit-scrollbar-button:single-button:hover {{
    background-color: {scroll_button_hover} !important;
}}
::-webkit-scrollbar-button:single-button:vertical:decrement {{
    background-image: url("{arrow_up}") !important;
}}
::-webkit-scrollbar-button:single-button:vertical:increment {{
    background-image: url("{arrow_down}") !important;
}}
::-webkit-scrollbar-button:single-button:horizontal:decrement {{
    background-image: url("{arrow_left}") !important;
}}
::-webkit-scrollbar-button:single-button:horizontal:increment {{
    background-image: url("{arrow_right}") !important;
}}
::-webkit-scrollbar-corner {{
    background: {scroll_track} !important;
}}
"""

        return (
            f":root {{ color-scheme: {scheme}; }}\n"
            f"html, body {{ background:{background} !important; color:{foreground} !important; }}\n"
            f"a:link {{ color:{link}; }} a:visited {{ color:{visited}; }} a:active {{ color:{active}; }}\n"
            "img, svg { max-width: 100%; }\n"
            + scrollbar_css
        )

    def apply_widget_theme(self) -> None:
        """Synchronisiert den QWebEngineView mit dem globalen Anwendungstheme."""
        bg = self.content_background_color()
        fg = self.content_foreground_color()
        palette = QPalette(self.web_view.palette())
        palette.setColor(QPalette.Window, bg)
        palette.setColor(QPalette.Base, bg)
        palette.setColor(QPalette.WindowText, fg)
        palette.setColor(QPalette.Text, fg)
        self.web_view.setPalette(palette)
        self.web_view.setAutoFillBackground(True)
        self.web_view.setStyleSheet(
            f"QWebEngineView#chm_content_view {{ "
            f"background:{bg.name()}; color:{fg.name()}; }}"
        )
        self.web_page.setBackgroundColor(bg)

    def apply_content_theme(self) -> None:
        self.apply_widget_theme()
        css = self.content_theme_css()
        background = self.content_background_color().name()
        foreground = self.content_foreground_color().name()
        script = (
            "(function(){"
            f"var id={json.dumps(self.CONTENT_THEME_STYLE_ID)};"
            "var s=document.getElementById(id);"
            "if(!s){s=document.createElement('style');s.id=id;"
            "(document.head||document.documentElement).appendChild(s);}"
            f"s.textContent={json.dumps(css)};"
            f"document.documentElement.style.backgroundColor={json.dumps(background)};"
            "if(document.body){"
            f"document.body.style.backgroundColor={json.dumps(background)};"
            f"document.body.style.color={json.dumps(foreground)};"
            "}"
            "})();"
        )
        self.web_page.runJavaScript(script)


    def set_dark_mode(self, enabled: bool) -> None:
        self.dark_mode_enabled = bool(enabled)
        self.settings.setValue("ui/dark_mode", self.dark_mode_enabled)
        self.apply_application_theme()
        self.apply_content_theme()

        if hasattr(self, "title_bar"):
            self.title_bar.update_state()

        for controller in getattr(
            self,
            "_toc_scrollbar_arrow_controllers",
            [],
        ):
            try:
                controller.first.update()
                controller.second.update()
                controller.reposition()
            except Exception:
                pass

        self.update()

    # ---- Persistente Fenster-/Splitter-Geometrie -------------------------
    def restore_ui_state(self) -> None:
        """Stellt Fenstergeometrie und Splitter vor dem ersten show() wieder her."""
        geometry = self.settings.value("ui/window_geometry")
        if geometry is not None:
            try:
                self.restoreGeometry(geometry)
            except (TypeError, RuntimeError):
                pass

        window_state = self.settings.value("ui/window_state")
        if window_state is not None:
            try:
                self.restoreState(window_state)
            except (TypeError, RuntimeError):
                pass

        splitter_state = self.settings.value("ui/main_splitter_state")
        if splitter_state is not None:
            try:
                self.splitter.restoreState(splitter_state)
            except (TypeError, RuntimeError):
                pass

    def save_ui_state(self) -> None:
        """Speichert Fenstergeometrie und Splitter unmittelbar vor dem Schließen."""
        self.settings.setValue("ui/window_geometry", self.saveGeometry())
        self.settings.setValue("ui/window_state", self.saveState())
        self.settings.setValue("ui/main_splitter_state", self.splitter.saveState())
        self.settings.setValue("ui/dark_mode", self.dark_mode_enabled)
        self.settings.sync()


    def cleanup_remote_asset_cache(self) -> None:
        """Entfernt den kompletten Remote-Asset-Cache zuverlässig.

        QTemporaryDir besitzt zwar AutoRemove, der Cache wird hier trotzdem
        explizit gelöscht, damit auch bei normalem QApplication-Shutdown keine
        chmviewer_remote_assets_* Verzeichnisse zurückbleiben.
        """
        self._closing = True
        self.remote_asset_inflight.clear()

        cache = getattr(self, "remote_asset_cache", None)
        if cache is None:
            return

        cache_path = ""
        try:
            cache_path = str(cache.path() or "")
        except Exception:
            cache_path = ""

        try:
            cache.setAutoRemove(True)
        except Exception:
            pass

        # Zuerst Qt selbst entfernen lassen.
        removed = False
        try:
            removed = bool(cache.remove())
        except Exception:
            removed = False

        # Fallback für Windows: falls Qt das Verzeichnis wegen eines noch
        # offenen Handles nicht vollständig entfernen konnte.
        if cache_path:
            path = Path(cache_path)
            if path.exists():
                try:
                    shutil.rmtree(path)
                    removed = True
                except OSError as exc:
                    print(
                        f"[CHM CLEANUP] Remote-Asset-Verzeichnis konnte "
                        f"nicht gelöscht werden: {path} :: {exc}",
                        flush=True,
                    )

        if cache_path and not Path(cache_path).exists():
            print(
                f"[CHM CLEANUP] Remote-Asset-Verzeichnis gelöscht: "
                f"{cache_path}",
                flush=True,
            )

    # ---- Remote-URL-/SVG-Unterstützung -----------------------------------
    def certificate_trusted_hosts(self) -> List[str]:
        raw = self.settings.value("network/trusted_certificate_hosts", [])
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        return sorted({
            str(value).strip().casefold()
            for value in raw
            if str(value).strip()
        })

    def is_certificate_host_trusted(self, host: str) -> bool:
        return str(host or "").casefold() in self.certificate_trusted_hosts()

    def trust_certificate_host(self, host: str) -> None:
        host = str(host or "").strip().casefold()
        if not host:
            return
        values = set(self.certificate_trusted_hosts())
        values.add(host)
        self.settings.setValue("network/trusted_certificate_hosts", sorted(values))
        self.settings.sync()

    def resolve_failed_remote_images(self) -> None:
        script = (
            "(function(){"
            "const result=[];"
            "document.querySelectorAll('img').forEach(function(img){"
            "const src=img.getAttribute('src')||'';"
            "if(!/^https?:\\/\\//i.test(src))return;"
            "if(img.dataset.chmRemoteBridged==='1')return;"
            "if(!img.complete||img.naturalWidth===0||img.naturalHeight===0){result.push(src);}"
            "});"
            "return Array.from(new Set(result));"
            "})();"
        )
        self.web_page.runJavaScript(script, self._remote_image_urls_found)

    def _remote_image_urls_found(self, urls) -> None:
        if not isinstance(urls, list):
            return
        for value in urls:
            url = str(value or "").strip()
            if not url or url in self.remote_asset_inflight:
                continue
            if not url.lower().startswith(("http://", "https://")):
                continue
            self.remote_asset_inflight.add(url)
            print(f"[CHM NETWORK] Remote-IMG Fallback: {url}", flush=True)
            threading.Thread(
                target=self._download_remote_asset_worker,
                args=(url,),
                daemon=True,
            ).start()

    def _download_remote_asset_worker(self, url: str) -> None:
        if getattr(self, "_closing", False):
            self.remote_asset_inflight.discard(url)
            return

        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 CHMViewer/1.0"
                    ),
                    "Accept": "image/svg+xml,image/*;q=0.9,*/*;q=0.5",
                },
                method="GET",
            )

            parsed = urlparse(url)
            context = None
            if (
                parsed.scheme.casefold() == "https"
                and self.is_certificate_host_trusted(parsed.hostname or "")
            ):
                context = ssl._create_unverified_context()

            with urllib.request.urlopen(request, timeout=15, context=context) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                content_type = (
                    response.headers.get("Content-Type", "")
                    .split(";", 1)[0]
                    .strip()
                    .casefold()
                )

            if len(data) > 16 * 1024 * 1024:
                raise ValueError("Remote-Grafik ist größer als 16 MiB.")

            probe = data[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()

            if content_type == "image/svg+xml" or b"<svg" in probe:
                suffix = ".svg"
            elif content_type == "image/png" or data.startswith(b"\x89PNG"):
                suffix = ".png"
            elif content_type in ("image/jpeg", "image/jpg") or data.startswith(b"\xff\xd8"):
                suffix = ".jpg"
            elif content_type == "image/gif" or data.startswith((b"GIF87a", b"GIF89a")):
                suffix = ".gif"
            elif content_type == "image/webp" or (
                len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            ):
                suffix = ".webp"
            else:
                raise ValueError(
                    "Serverantwort ist kein erkennbares Bild. "
                    f"Content-Type: {content_type or '(fehlt)'}"
                )

            # Während des Programm-Shutdowns keine Cache-Datei mehr erzeugen.
            if getattr(self, "_closing", False):
                self.remote_asset_inflight.discard(url)
                return

            cache_dir = Path(self.remote_asset_cache.path())
            if not cache_dir.is_dir():
                self.remote_asset_inflight.discard(url)
                return

            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            target = cache_dir / f"{digest}{suffix}"
            target.write_bytes(data)

            local_url = QUrl.fromLocalFile(str(target)).toString()
            print(
                f"[CHM NETWORK] Remote-Bild lokal gespiegelt: {url} -> {target}",
                flush=True,
            )
            self.remote_asset_ready.emit(url, local_url)
        except Exception as exc:
            self.remote_asset_failed.emit(url, str(exc))

    def _apply_resolved_remote_asset(self, original_url: str, local_url: str) -> None:
        self.remote_asset_inflight.discard(original_url)
        script = (
            "(function(){"
            f"const original={json.dumps(original_url)};"
            f"const local={json.dumps(local_url)};"
            "document.querySelectorAll('img').forEach(function(img){"
            "const src=img.getAttribute('src')||'';"
            "if(src===original||img.src===original){"
            "img.dataset.chmRemoteBridged='1';"
            "img.dataset.chmRemoteOriginal=original;"
            "img.src=local;"
            "}"
            "});"
            "})();"
        )
        self.web_page.runJavaScript(script)
        self.status_bar.showMessage(
            "Remote-Grafik über lokalen SVG/Bild-Bridge geladen",
            5000,
        )

    def _report_remote_asset_failure(self, url: str, reason: str) -> None:
        self.remote_asset_inflight.discard(url)
        print(
            f"[CHM NETWORK] Remote-Grafik fehlgeschlagen: {url} :: {reason}",
            flush=True,
        )
        self.status_bar.showMessage(
            f"Remote-Grafik konnte nicht geladen werden: {reason}",
            8000,
        )

    # ---- Open / metadata --------------------------------------------------
    def choose_chm(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "CHM-Hilfedatei öffnen",
            "",
            "CHM-Hilfedateien (*.chm);;Alle Dateien (*)",
        )
        if filename:
            self.open_chm(filename)

    def choose_help_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Entpacktes Hilfe-Verzeichnis öffnen", "")
        if directory:
            self.open_help_directory(directory)

    def open_chm(self, filename: str) -> bool:
        source = Path(filename).expanduser().resolve()
        if not source.is_file():
            QMessageBox.warning(self, "CHM Viewer", f"Datei nicht gefunden:\n{source}")
            return False

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_bar.showMessage("CHM-Datei wird entpackt …")
        QApplication.processEvents()
        new_temporary: Optional[tempfile.TemporaryDirectory] = None
        try:
            new_temporary = tempfile.TemporaryDirectory(prefix="d64_chm_viewer_")
            root = Path(new_temporary.name)
            ChmExtractor.extract(source, root)
            topics, keywords, home_local = self.read_metadata(root)
            context_id_map = read_chm_context_map(root)
        except Exception as exc:
            if new_temporary is not None:
                new_temporary.cleanup()
            QMessageBox.critical(self, "CHM Viewer", str(exc))
            self.status_bar.showMessage("CHM-Datei konnte nicht geöffnet werden", 6000)
            return False
        finally:
            QApplication.restoreOverrideCursor()

        self._adopt_content(root, source, topics, keywords, home_local, context_id_map, new_temporary)
        return True

    def open_help_directory(self, directory: str, display_name: str = "Hilfe") -> bool:
        root = Path(directory).expanduser().resolve()
        if not root.is_dir():
            QMessageBox.warning(self, "CHM Viewer", f"Hilfe-Verzeichnis nicht gefunden:\n{root}")
            return False
        try:
            topics, keywords, home_local = self.read_metadata(root)
            context_id_map = read_chm_context_map(root)
        except Exception as exc:
            QMessageBox.critical(self, "CHM Viewer", str(exc))
            return False

        project = find_chm_file_by_suffix(root, ".hhp")
        source = project if project is not None else root / "index.html"
        self._adopt_content(root, source, topics, keywords, home_local, context_id_map, None)
        self.setWindowTitle(f"{display_name} – CHM Viewer (c) 2026 Jens Kallup")
        return True

    def _adopt_content(
        self,
        root: Path,
        source: Path,
        topics: List[ChmSitemapEntry],
        keywords: List[ChmSitemapEntry],
        home_local: str,
        context_id_map: Dict[int, str],
        temporary: Optional[tempfile.TemporaryDirectory],
    ) -> None:
        old_temporary = self.temporary
        self.web_view.setUrl(QUrl("about:blank"))
        QApplication.processEvents()

        self.temporary = temporary
        self.content_root = root
        self.chm_path = source
        self.home_local = home_local
        self.context_id_map = dict(context_id_map)

        if old_temporary is not None:
            try:
                old_temporary.cleanup()
            except OSError:
                pass

        self.populate_tree(self.topics_tab.tree, topics)
        self.populate_tree(self.keywords_tab.tree, keywords)
        self.load_favorites()
        self.tabs.setCurrentWidget(self.topics_tab)
        self.file_status.setText(str(source))
        self.setWindowTitle(f"{source.name} – CHM Viewer")

        topic_count = self.tree_count(self.topics_tab.tree)
        keyword_count = self.tree_count(self.keywords_tab.tree)
        self.status_bar.showMessage(f"{topic_count} Themen und {keyword_count} Schlüsselwörter geladen", 6000)

        first_item = self.first_local_item(self.topics_tab.tree)
        if first_item is not None:
            self.topics_tab.tree.setCurrentItem(first_item)
            self.topics_tab.tree.scrollToItem(first_item)
        elif self.home_local:
            self.load_local(self.home_local)
        else:
            self.show_empty_page("Keine anzeigbare Hilfeseite gefunden.")
        self.update_navigation()

        if (
            self.pending_local
            or self.pending_keyword
            or self.pending_context_word
            or self.pending_context_id
        ):
            QTimer.singleShot(0, self.apply_pending_help_request)

    def read_metadata(self, root: Path):
        project = find_chm_file_by_suffix(root, ".hhp")
        options = read_chm_project_options(project)
        contents = self.metadata_file(root, options.get("contents file", ""), ".hhc")
        index = self.metadata_file(root, options.get("index file", ""), ".hhk")
        topics = parse_chm_sitemap(contents)
        keywords = parse_chm_sitemap(index)

        if not topics:
            html_files = [
                p for p in iter_chm_files(root)
                if p.is_file() and p.suffix.casefold() in (".html", ".htm")
            ]
            html_files.sort(key=lambda p: str(p.relative_to(root)).casefold())
            topics = [ChmSitemapEntry(p.stem, p.relative_to(root).as_posix()) for p in html_files]

        home_local = self.find_index(root)
        if not home_local:
            default_topic = options.get("default topic", "")
            relative, fragment = clean_chm_local(default_topic)
            if relative and resolve_chm_path(root, relative):
                home_local = relative + (("#" + fragment) if fragment else "")
        if not home_local:
            home_local = self.first_entry_local(topics)
        return topics, keywords, home_local

    def metadata_file(self, root: Path, configured: str, suffix: str) -> Optional[Path]:
        if configured:
            relative, _ = clean_chm_local(configured)
            resolved = resolve_chm_path(root, relative) if relative else None
            if resolved is not None:
                return resolved
        return find_chm_file_by_suffix(root, suffix)

    def find_index(self, root: Path) -> str:
        candidates = [p for p in iter_chm_files(root) if p.is_file() and p.name.casefold() in ("index.html", "index.htm")]
        if not candidates:
            return ""
        result = min(candidates, key=lambda p: (len(p.relative_to(root).parts), str(p).casefold()))
        return result.relative_to(root).as_posix()

    def first_entry_local(self, entries: List[ChmSitemapEntry]) -> str:
        for entry in entries:
            if entry.local:
                return entry.local
            nested = self.first_entry_local(entry.children)
            if nested:
                return nested
        return ""

    # ---- Trees / navigation ---------------------------------------------
    def populate_tree(self, tree: QTreeWidget, entries: List[ChmSitemapEntry]) -> None:
        tree.blockSignals(True)
        tree.clear()

        def add_entries(parent, values):
            for entry in values:
                item = QTreeWidgetItem(parent, [entry.title])
                item.setData(0, CHM_ROLE_LOCAL, entry.local)
                item.setData(0, CHM_ROLE_TITLE, entry.title)
                item.setIcon(0, tree.style().standardIcon(
                    QStyle.SP_DirClosedIcon if entry.children else QStyle.SP_FileIcon
                ))
                if entry.children:
                    add_entries(item, entry.children)

        add_entries(tree, entries)
        tree.blockSignals(False)
        if tree.topLevelItemCount():
            tree.topLevelItem(0).setExpanded(True)

    def tree_count(self, tree: QTreeWidget) -> int:
        iterator = QTreeWidgetItemIterator(tree)
        count = 0
        while iterator.value() is not None:
            count += 1
            iterator += 1
        return count

    def first_local_item(self, tree: QTreeWidget):
        iterator = QTreeWidgetItemIterator(tree)
        while iterator.value() is not None:
            item = iterator.value()
            if str(item.data(0, CHM_ROLE_LOCAL) or "").strip():
                return item
            iterator += 1
        return None

    def tree_item_changed(self, current, _previous) -> None:
        if current is None:
            return
        local = str(current.data(0, CHM_ROLE_LOCAL) or "").strip()
        if local:
            self.load_local(local)

    def find_first(self, tree: QTreeWidget, text: str) -> None:
        if not text:
            return
        needle = text.casefold()
        iterator = QTreeWidgetItemIterator(tree)
        while iterator.value() is not None:
            item = iterator.value()
            if needle in item.text(0).casefold():
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                tree.setCurrentItem(item)
                tree.scrollToItem(item)
                self.status_bar.showMessage(f"Treffer: {item.text(0)}", 4000)
                return
            iterator += 1
        QApplication.beep()
        self.status_bar.showMessage(f"Kein Treffer für „{text}“", 5000)

    def local_url(self, value: str) -> Optional[QUrl]:
        if self.content_root is None:
            return None
        relative, fragment = clean_chm_local(value)
        if not relative:
            return None
        target = resolve_chm_path(self.content_root, relative)
        if target is None:
            return None
        url = QUrl.fromLocalFile(str(target))
        if fragment:
            url.setFragment(fragment)
        return url

    def load_local(self, value: str) -> None:
        url = self.local_url(value)
        if url is None:
            self.status_bar.showMessage(f"Hilfeseite nicht gefunden: {value}", 6000)
            return
        self.web_view.setUrl(url)

    def go_home(self) -> None:
        if self.home_local:
            self.load_local(self.home_local)

    def show_empty_page(self, message: str = "Öffne eine CHM-Hilfedatei.") -> None:
        css = self.content_theme_css()
        self.web_view.setHtml(
            "<html><head><style id='" + self.CONTENT_THEME_STYLE_ID + "'>" + css + "</style></head>"
            "<body style='font-family:sans-serif;margin:3em'>"
            "<h2>CHM Viewer</h2>"
            f"<p>{html.escape(message)}</p>"
            "</body></html>"
        )

    # ---- Context help ----------------------------------------------------
    def set_pending_request(
        self,
        *,
        language: str = "",
        topic: str = "",
        context_id: int = 0,
        local: str = "",
        keyword: str = "",
    ) -> None:
        """Speichert einen Hilfeaufruf bis CHM/Help-Verzeichnis geladen ist.

        Priorität beim späteren Öffnen:
          1. direkte lokale Hilfeseite (HH_DISPLAY_TOPIC-artig)
          2. numerische Context-ID mit Topic-Fallback
          3. explizites Keyword
          4. Topic-/Wortsuche
        """
        self.pending_context_language = str(language or "").casefold()
        self.pending_context_word = str(topic or "").strip()
        self.pending_context_id = max(0, int(context_id or 0))
        self.pending_local = str(local or "").strip()
        self.pending_keyword = str(keyword or "").strip()

    def set_pending_context(self, language: str, word: str, context_id: int = 0) -> None:
        """Abwärtskompatibler Alias für ältere Aufrufer des Python-Moduls."""
        self.set_pending_request(
            language=language,
            topic=word,
            context_id=context_id,
        )

    def apply_pending_help_request(self) -> bool:
        """Führt einen zuvor gespeicherten modernen oder Legacy-Hilfeaufruf aus."""
        if self.pending_local:
            local = self.pending_local
            if self._select_context_local(local):
                self.status_bar.showMessage(
                    f"Hilfethema: {local}",
                    5000,
                )
                return True
            self.status_bar.showMessage(
                f"Hilfethema nicht gefunden: {local}",
                5000,
            )

        if self.pending_context_id or self.pending_context_word:
            if self.open_context_topic(
                self.pending_context_language,
                self.pending_context_word,
                self.pending_context_id,
            ):
                return True

        if self.pending_keyword:
            return self.open_keyword_topic(self.pending_keyword)

        return False

    def open_keyword_topic(self, keyword: str) -> bool:
        """Öffnet bevorzugt einen exakten Eintrag aus dem CHM-Schlüsselwortindex."""
        needle = str(keyword or "").strip().casefold()
        if not needle:
            return False

        # Zuerst ausschließlich im Schlüsselwortindex suchen.
        best_item = None
        best_score = -1
        iterator = QTreeWidgetItemIterator(self.keywords_tab.tree)
        while iterator.value() is not None:
            item = iterator.value()
            title = item.text(0).strip().casefold()
            local = str(item.data(0, CHM_ROLE_LOCAL) or "")
            score = 0
            if title == needle:
                score = 100
            elif title.startswith(needle):
                score = 80
            elif needle in title:
                score = 60

            if local and score > best_score:
                best_item = item
                best_score = score
            iterator += 1

        if best_item is not None and best_score > 0:
            parent = best_item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()

            self.keywords_tab.tree.setCurrentItem(best_item)
            self.keywords_tab.tree.scrollToItem(best_item)
            self.tabs.setCurrentWidget(self.keywords_tab)

            local = str(best_item.data(0, CHM_ROLE_LOCAL) or "")
            self.load_local(local)
            self.status_bar.showMessage(
                f"Schlüsselwort: {keyword}",
                5000,
            )
            return True

        # Fallback: dieselbe Suchlogik wie ein modernes Topic.
        return self.open_context_topic("", keyword, 0)

    def _select_context_local(self, local: str) -> bool:
        relative, fragment = clean_chm_local(local)
        if not relative or resolve_chm_path(self.content_root, relative) is None:
            return False
        wanted = relative.casefold()
        best_item = None
        for tree in (self.keywords_tab.tree, self.topics_tab.tree):
            iterator = QTreeWidgetItemIterator(tree)
            while iterator.value() is not None:
                item = iterator.value()
                item_relative, _ = clean_chm_local(str(item.data(0, CHM_ROLE_LOCAL) or ""))
                if item_relative.casefold() == wanted:
                    best_item = item
                    break
                iterator += 1
            if best_item is not None:
                break

        if best_item is not None:
            parent = best_item.parent()
            while parent is not None:
                parent.setExpanded(True)
                parent = parent.parent()
            tree = best_item.treeWidget()
            tree.setCurrentItem(best_item)
            tree.scrollToItem(best_item)
            self.tabs.setCurrentWidget(self.keywords_tab if tree is self.keywords_tab.tree else self.topics_tab)

        self.load_local(relative + (("#" + fragment) if fragment else ""))
        return True

    def open_context_topic(self, language: str, word: str, context_id: int = 0) -> bool:
        needle = str(word or "").strip().casefold()
        language_name = str(language or "").strip().casefold()
        context_id = max(0, int(context_id or 0))

        if context_id:
            local = str(self.context_id_map.get(context_id, "") or "")
            if local and self._select_context_local(local):
                self.status_bar.showMessage(f"Kontexthilfe-ID {context_id}: {word or local}", 5000)
                return True

        if not needle:
            self.status_bar.showMessage(f"Keine CHM-Zuordnung für Context-ID {context_id}", 5000)
            return False

        best_item = None
        best_score = -1
        for tree in (self.keywords_tab.tree, self.topics_tab.tree):
            iterator = QTreeWidgetItemIterator(tree)
            while iterator.value() is not None:
                item = iterator.value()
                title = item.text(0).strip().casefold()
                local = str(item.data(0, CHM_ROLE_LOCAL) or "").casefold()
                score = 0
                if title == needle:
                    score += 100
                elif needle in title:
                    score += 50
                if local and Path(local.split("#", 1)[0]).stem.casefold() == needle:
                    score += 80
                if score and language_name and language_name in local:
                    score += 20
                if score > best_score and local:
                    best_item = item
                    best_score = score
                iterator += 1

        if best_item is None or best_score <= 0:
            self.status_bar.showMessage(f"Kein Hilfethema für „{word}“ gefunden", 5000)
            return False

        parent = best_item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        tree = best_item.treeWidget()
        tree.setCurrentItem(best_item)
        tree.scrollToItem(best_item)
        self.tabs.setCurrentWidget(self.keywords_tab if tree is self.keywords_tab.tree else self.topics_tab)
        self.load_local(str(best_item.data(0, CHM_ROLE_LOCAL) or ""))
        return True

    # ---- Favorites -------------------------------------------------------
    def current_local(self) -> str:
        if self.content_root is None:
            return ""
        url = self.web_view.url()
        if not url.isLocalFile():
            return ""
        try:
            relative = Path(url.toLocalFile()).resolve().relative_to(self.content_root.resolve())
        except (OSError, ValueError):
            return ""
        result = relative.as_posix()
        if url.fragment():
            result += "#" + url.fragment()
        return result

    def favorites_key(self) -> str:
        if self.chm_path is None:
            return ""
        digest = hashlib.sha256(str(self.chm_path).casefold().encode("utf-8")).hexdigest()
        return "chm/favorites/" + digest

    def favorite_values(self) -> List[Dict[str, str]]:
        key = self.favorites_key()
        if not key:
            return []
        raw = self.settings.value(key, "[]", type=str)
        try:
            values = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(values, list):
            return []
        return [
            {"title": str(item.get("title", "")), "local": str(item.get("local", ""))}
            for item in values
            if isinstance(item, dict) and item.get("local")
        ]

    def save_favorite_values(self, values: List[Dict[str, str]]) -> None:
        key = self.favorites_key()
        if key:
            self.settings.setValue(key, json.dumps(values, ensure_ascii=False))

    def load_favorites(self) -> None:
        tree = self.favorites_tab.tree
        tree.blockSignals(True)
        tree.clear()
        for favorite in self.favorite_values():
            item = QTreeWidgetItem(tree, [favorite["title"] or favorite["local"]])
            item.setData(0, CHM_ROLE_LOCAL, favorite["local"])
            item.setData(0, CHM_ROLE_TITLE, favorite["title"])
            item.setIcon(0, tree.style().standardIcon(QStyle.SP_FileIcon))
        tree.blockSignals(False)
        self.update_navigation()

    def add_current_favorite(self) -> None:
        local = self.current_local()
        if not local:
            self.status_bar.showMessage("Die aktuelle Seite kann nicht gespeichert werden", 5000)
            return
        title = self.web_view.title().strip() or Path(local.split("#", 1)[0]).name
        values = self.favorite_values()
        if any(v["local"].casefold() == local.casefold() for v in values):
            self.status_bar.showMessage("Diese Seite ist bereits als Favorit gespeichert", 4000)
            return
        values.append({"title": title, "local": local})
        self.save_favorite_values(values)
        self.load_favorites()
        self.status_bar.showMessage(f"Favorit gespeichert: {title}", 4000)

    def remove_current_favorite(self) -> None:
        item = self.favorites_tab.tree.currentItem()
        if item is None:
            return
        local = str(item.data(0, CHM_ROLE_LOCAL) or "")
        values = [v for v in self.favorite_values() if v["local"].casefold() != local.casefold()]
        self.save_favorite_values(values)
        self.load_favorites()
        self.status_bar.showMessage("Favorit entfernt", 3000)

    # ---- Commands / lifecycle -------------------------------------------
    def show_page_source(self) -> None:
        """Öffnet den Seitenquelltext im Standard-Texteditor des Systems.

        Wir verwenden QWebEnginePage.toHtml(), damit sowohl lokale CHM-Seiten
        als auch remote geladene Seiten funktionieren. Der Quelltext wird als
        UTF-8-Textdatei geschrieben; dadurch öffnet Windows nicht versehentlich
        den Standardbrowser für eine .html-Datei.
        """
        self.status_bar.showMessage("Seitenquelltext wird gelesen …")

        def receive_source(source: str) -> None:
            try:
                title = self.web_view.title().strip()
                if not title:
                    title = "page"

                safe_title = re.sub(
                    r"[^A-Za-z0-9_.-]+",
                    "_",
                    title,
                ).strip("._") or "page"

                source_dir = Path(tempfile.gettempdir()) / "chmviewer_source"
                source_dir.mkdir(parents=True, exist_ok=True)

                source_file = source_dir / (
                    f"{safe_title}_{int(time.time() * 1000)}.html.txt"
                )
                source_file.write_text(
                    source,
                    encoding="utf-8",
                    errors="replace",
                )
                self.source_temp_files.append(source_file)

                opened = QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(source_file))
                )
                if opened:
                    self.status_bar.showMessage(
                        f"Quelltext im Standard-Editor geöffnet: {source_file.name}",
                        5000,
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Show Source",
                        "Der Standard-Editor konnte nicht geöffnet werden.\\n\\n"
                        f"Quelltextdatei:\\n{source_file}",
                    )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Show Source",
                    f"Der Seitenquelltext konnte nicht geöffnet werden:\\n{exc}",
                )

        self.web_page.toHtml(receive_source)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Über CHM Viewer",
            "<h3>CHM Viewer</h3>"
            "<p>Qt5/Chromium-basierter CHM-Viewer mit Themen, Schlüsselwörtern, Favoriten, SVG- und Remote-URL-Unterstützung.</p>"
            "<p>CHM-Dateien werden temporär entpackt und mit QWebEngine angezeigt.</p>",
        )

    def load_finished(self, success: bool) -> None:
        self.apply_content_theme()
        if success:
            self.status_bar.showMessage(
            "Seite geladen" if success else "Die Seite konnte nicht geladen werden",
            2500 if success else 5000,
        )
        if success:
            QTimer.singleShot(350, self.resolve_failed_remote_images)
            QTimer.singleShot(1200, self.resolve_failed_remote_images)
        self.update_navigation()

    def title_changed(self, title: str) -> None:
        if self.chm_path is not None:
            visible_title = title.strip() or self.chm_path.name
            self.setWindowTitle(f"{visible_title} – CHM Viewer")
        if hasattr(self, "title_bar"):
            self.title_bar.update()

    def update_navigation(self) -> None:
        history = self.web_view.history()
        has_content = self.content_root is not None
        self.home_action.setEnabled(has_content and bool(self.home_local))
        self.back_action.setEnabled(history.canGoBack())
        self.forward_action.setEnabled(history.canGoForward())
        self.copy_action.setEnabled(has_content)
        self.source_action.setEnabled(has_content)
        self.add_favorite_button.setEnabled(has_content)
        self.remove_favorite_button.setEnabled(self.favorites_tab.tree.currentItem() is not None)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        # Exakt 3 Pixel sichtbarer Rahmen.
        painter = QPainter(self)
        pen = QPen(
            self.window_border_color(),
            self.WINDOW_BORDER_WIDTH,
        )
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        inset = self.WINDOW_BORDER_WIDTH / 2.0
        painter.drawRect(
            int(inset),
            int(inset),
            max(0, int(self.width() - self.WINDOW_BORDER_WIDTH)),
            max(0, int(self.height() - self.WINDOW_BORDER_WIDTH)),
        )
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_resize_handles()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            if hasattr(self, "title_bar"):
                self.title_bar.update_state()
            self._layout_resize_handles()

    def closeEvent(self, event) -> None:
        # Vor jeglichem Aufräumen den sichtbaren Benutzerzustand sichern.
        self.save_ui_state()

        # Ab jetzt dürfen Hintergrund-Downloads keine neuen Cache-Dateien
        # mehr anlegen.
        self._closing = True

        # QWebEngine zuerst von eventuell lokal gespiegelten Remote-Dateien
        # lösen, damit Windows keine offenen Handles auf dem Cache behält.
        self.web_view.setUrl(QUrl("about:blank"))
        QApplication.processEvents()

        self.cleanup_remote_asset_cache()

        if self.temporary is not None:
            try:
                self.temporary.cleanup()
            except OSError:
                pass
            self.temporary = None

        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Externe Hilfe-Schnittstelle
#
# Modern:
#   chmviewer.py help.chm --topic PRINT --language basic --context-id 2101
#
# Rückwärtskompatibel:
#   chmviewer.py help.chm --word PRINT
#
# Legacy / hh.exe-artig:
#   chmviewer.py "help.chm::/basic/print.html"
#   chmviewer.py -mapid 2101 help.chm
#   chmviewer.py -keyword PRINT help.chm
#   chmviewer.py /context 2101 help.chm
#   chmviewer.py /topic basic/print.html help.chm
#
# HTML-Help-Bridge:
#   chmviewer.py help.chm --hh-command HH_HELP_CONTEXT --hh-data 2101
#   chmviewer.py help.chm --hh-command HH_DISPLAY_TOPIC --hh-data basic/print.html
#   chmviewer.py help.chm --hh-command HH_KEYWORD_LOOKUP --hh-data PRINT
# ---------------------------------------------------------------------------

HH_DISPLAY_TOPIC = 0x0000
HH_KEYWORD_LOOKUP = 0x000D
HH_HELP_CONTEXT = 0x000F


def normalize_legacy_argv(argv: Sequence[str]) -> List[str]:
    """Übersetzt gebräuchliche Legacy-Schreibweisen in unser CLI-Format.

    Die Funktion verändert bewusst keine normalen Dateipfade.
    Windows-/Delphi-artige Slash-Schalter werden nur bei exakt bekannten
    Tokens umgesetzt.
    """
    aliases = {
        "/context": "--context-id",
        "/contextid": "--context-id",
        "/mapid": "--context-id",
        "/keyword": "--keyword",
        "/topic": "--local",
        "/local": "--local",
        "/language": "--language",
        "-context": "--context-id",
        "-contextid": "--context-id",
        "-mapid": "--context-id",
        "-keyword": "--keyword",
        "-topic": "--local",
        "-local": "--local",
        "-language": "--language",
    }

    result: List[str] = []
    for raw in argv:
        token = str(raw)
        translated = aliases.get(token.casefold())
        result.append(translated if translated is not None else token)
    return result


def split_chm_reference(value: str) -> Tuple[str, str]:
    """Zerlegt CHM-Referenzen wie help.chm::/topic.htm.

    Ebenfalls akzeptiert:
      mk:@MSITStore:help.chm::/topic.htm
      ms-its:help.chm::/topic.htm
    """
    raw = str(value or "").strip().strip('"')
    lowered = raw.casefold()

    for prefix in ("mk:@msitstore:", "ms-its:"):
        if lowered.startswith(prefix):
            raw = raw[len(prefix):]
            break

    if "::" not in raw:
        return raw, ""

    chm_file, local = raw.split("::", 1)
    local = local.strip()
    while local.startswith(("/", "\\")):
        local = local[1:]
    return chm_file.strip(), local


def normalize_hh_command(command: str) -> Optional[int]:
    """Akzeptiert symbolische und numerische HTML-Help-Kommandos."""
    value = str(command or "").strip()
    if not value:
        return None

    names = {
        "HH_DISPLAY_TOPIC": HH_DISPLAY_TOPIC,
        "DISPLAY_TOPIC": HH_DISPLAY_TOPIC,
        "TOPIC": HH_DISPLAY_TOPIC,
        "HH_KEYWORD_LOOKUP": HH_KEYWORD_LOOKUP,
        "KEYWORD_LOOKUP": HH_KEYWORD_LOOKUP,
        "KEYWORD": HH_KEYWORD_LOOKUP,
        "HH_HELP_CONTEXT": HH_HELP_CONTEXT,
        "HELP_CONTEXT": HH_HELP_CONTEXT,
        "CONTEXT": HH_HELP_CONTEXT,
    }

    upper = value.upper()
    if upper in names:
        return names[upper]

    try:
        return int(value, 0)
    except ValueError:
        return None


def apply_hh_bridge_arguments(args, parser: argparse.ArgumentParser) -> None:
    """Überträgt --hh-command/--hh-data auf die normale interne Anfrage."""
    if not args.hh_command:
        return

    command = normalize_hh_command(args.hh_command)
    if command is None:
        parser.error(f"Unbekanntes HTML-Help-Kommando: {args.hh_command}")

    data = str(args.hh_data or "").strip()

    if command == HH_DISPLAY_TOPIC:
        if data:
            args.local = data
        return

    if command == HH_HELP_CONTEXT:
        if not data:
            parser.error("HH_HELP_CONTEXT benötigt --hh-data <Context-ID>.")
        try:
            args.context_id = int(data, 0)
        except ValueError:
            parser.error(f"Ungültige Context-ID: {data}")
        return

    if command == HH_KEYWORD_LOOKUP:
        if not data:
            parser.error("HH_KEYWORD_LOOKUP benötigt --hh-data <Schlüsselwort>.")
        args.keyword = data
        return

    parser.error(
        "Dieses HTML-Help-Kommando wird vom Kompatibilitäts-Layer "
        f"noch nicht unterstützt: {args.hh_command}"
    )


def parse_args(argv=None):
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    raw_argv = normalize_legacy_argv(raw_argv)

    parser = argparse.ArgumentParser(
        description="Qt5 CHM Viewer mit moderner und Legacy-/Delphi-Schnittstelle"
    )

    parser.add_argument(
        "path",
        nargs="?",
        help=(
            "CHM-Datei, entpacktes Hilfe-Verzeichnis oder "
            "Legacy-Referenz help.chm::/topic.html"
        ),
    )

    theme_group = parser.add_mutually_exclusive_group()
    theme_group.add_argument(
        "--dark",
        dest="dark_mode",
        action="store_true",
        help="Dark Mode erzwingen",
    )
    theme_group.add_argument(
        "--light",
        dest="dark_mode",
        action="store_false",
        help="Light Mode erzwingen",
    )
    parser.set_defaults(dark_mode=None)

    # Modernes Format. --word bleibt als kompatibler Alias erhalten.
    parser.add_argument(
        "--topic",
        "--word",
        dest="topic",
        default="",
        help="Themen-/Kontextwort; --word bleibt als Alias erhalten",
    )
    parser.add_argument(
        "--language",
        default="",
        help="Sprache zur Verfeinerung einer Topic-Suche",
    )
    parser.add_argument(
        "--context-id",
        "--mapid",
        dest="context_id",
        type=lambda value: int(value, 0),
        default=0,
        help="numerische CHM Context-ID",
    )
    parser.add_argument(
        "--local",
        default="",
        help="direkter interner HTML-Pfad innerhalb der CHM",
    )
    parser.add_argument(
        "--keyword",
        default="",
        help="Schlüsselwort aus dem CHM-Index",
    )

    # Expliziter Bridge-Modus für Wrapper, die HTML-Help-Kommandos abbilden.
    parser.add_argument(
        "--hh-command",
        default="",
        help=(
            "HTML-Help-Kommando, z.B. HH_HELP_CONTEXT, "
            "HH_DISPLAY_TOPIC oder HH_KEYWORD_LOOKUP"
        ),
    )
    parser.add_argument(
        "--hh-data",
        default="",
        help="Daten zum --hh-command",
    )

    args = parser.parse_args(raw_argv)

    # Legacy-Dateireferenz: "foo.chm::/bar.htm"
    if args.path:
        parsed_path, parsed_local = split_chm_reference(args.path)
        args.path = parsed_path
        if parsed_local and not args.local:
            args.local = parsed_local

    apply_hh_bridge_arguments(args, parser)
    return args


def main(argv=None) -> int:
    args = parse_args(argv)

    qt_argv = sys.argv if argv is None else [sys.argv[0], *argv]
    app = QApplication(qt_argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)

    window = MainWindow(dark_mode=args.dark_mode)

    # Zweite Cleanup-Sicherung: auch ein QApplication-Shutdown, der nicht
    # direkt über MainWindow.closeEvent() läuft, entfernt Remote-Assets.
    app.aboutToQuit.connect(window.cleanup_remote_asset_cache)

    if (
        args.topic
        or args.context_id
        or args.local
        or args.keyword
    ):
        window.set_pending_request(
            language=args.language,
            topic=args.topic,
            context_id=args.context_id,
            local=args.local,
            keyword=args.keyword,
        )

    window.show()

    if args.path:
        path = Path(args.path).expanduser()
        if path.is_dir():
            QTimer.singleShot(
                0,
                lambda p=str(path): window.open_help_directory(p),
            )
        else:
            QTimer.singleShot(
                0,
                lambda p=str(path): window.open_chm(p),
            )

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
