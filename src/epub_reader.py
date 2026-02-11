import os
import shutil
import sys
import tempfile
import threading
import traceback

from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from kokoro import KPipeline
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView

from .player import TtsPlayer
from .state import ReaderState


class EpubReaderApp(QtWidgets.QMainWindow):
    status_changed = Signal(str)
    error_message = Signal(str, str)
    controls_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("EPUB Reader + Kokoro TTS")
        self.pipeline = KPipeline(lang_code="a")
        self.state = ReaderState()
        self.state.load()
        self.player = TtsPlayer(self.pipeline)
        self.player.on_state = self._on_player_state
        self.chapters = []
        self.book_dir = None

        self._build_ui()
        self._wire_signals()
        self._load_saved_book()

    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QtWidgets.QHBoxLayout()
        self.open_button = QtWidgets.QPushButton("Open EPUB")
        self.play_button = QtWidgets.QPushButton("Play")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.resume_button = QtWidgets.QPushButton("Resume")
        self.stop_button = QtWidgets.QPushButton("Stop")
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.play_button)
        toolbar.addWidget(self.pause_button)
        toolbar.addWidget(self.resume_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.chapter_list = QtWidgets.QListWidget()
        self.chapter_list.setMinimumWidth(220)
        self.web_view = QWebEngineView()
        splitter.addWidget(self.chapter_list)
        splitter.addWidget(self.web_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        self.status = QtWidgets.QLabel("Ready")
        layout.addWidget(self.status)

        self.setCentralWidget(central)
        self._update_controls()

        self.open_button.clicked.connect(self.open_epub)
        self.play_button.clicked.connect(self.play_selected)
        self.pause_button.clicked.connect(self.pause)
        self.resume_button.clicked.connect(self.resume)
        self.stop_button.clicked.connect(self.stop)
        self.chapter_list.currentRowChanged.connect(self._show_chapter)
        self.web_view.loadFinished.connect(self._apply_reader_styles)

    def _wire_signals(self):
        self.status_changed.connect(self._set_status)
        self.error_message.connect(self._show_error)
        self.controls_changed.connect(self._update_controls)

    def _set_status(self, message):
        self.status.setText(message)

    def _on_player_state(self):
        self.controls_changed.emit()

    def _update_controls(self):
        if self.player.is_playing and not self.player.is_paused:
            self.play_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
        elif self.player.is_paused:
            self.play_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
        else:
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
        can_stop = self.player.is_playing or self.player.is_paused or bool(self.player.text)
        self.stop_button.setEnabled(bool(can_stop))

    def _load_saved_book(self):
        if not self.state.book_path:
            return
        if not os.path.exists(self.state.book_path):
            return
        self._load_epub(self.state.book_path)
        if self.chapters:
            index = min(self.state.chapter_index, len(self.chapters) - 1)
            self.chapter_list.setCurrentRow(index)
            self.chapter_list.scrollToItem(self.chapter_list.item(index))
            self._show_chapter(index)

    def open_epub(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open EPUB",
            "",
            "EPUB files (*.epub)",
        )
        if not path:
            return
        self._load_epub(path)

    def _load_epub(self, path):
        try:
            self.chapters = self._extract_chapters(path)
        except Exception as exc:
            print("EPUB load failed:", file=sys.stderr)
            traceback.print_exc()
            self.error_message.emit("EPUB Error", f"Failed to load EPUB:\n{exc}")
            return
        self.state.book_path = path
        self.state.chapter_index = 0
        self.state.offset_ms = 0
        self.state.save()
        self._refresh_chapter_list()
        self._show_chapter(0)
        self._set_status(f"Loaded: {os.path.basename(path)}")

    def _refresh_chapter_list(self):
        self.chapter_list.clear()
        for chapter in self.chapters:
            self.chapter_list.addItem(chapter["title"])
        if self.chapters:
            self.chapter_list.setCurrentRow(0)

    def _show_chapter(self, index):
        if index is None or index < 0 or index >= len(self.chapters):
            return
        chapter = self.chapters[index]
        self.web_view.setUrl(QUrl.fromLocalFile(chapter["html_path"]))
        self.state.chapter_index = index
        self.state.offset_ms = 0
        self.state.save()
        self.player.stop()
        self._set_status(f"Selected: {chapter['title']}")

    def _apply_reader_styles(self, ok):
        if not ok:
            return
        css = (
            "img { max-width: 100% !important; height: auto !important; } "
            "body { overflow-wrap: anywhere; word-wrap: break-word; } "
            "pre, code { white-space: pre-wrap; }"
        )
        script = (
            "(function() {"
            "  var style = document.getElementById('copilot-reader-style');"
            "  if (!style) {"
            "    style = document.createElement('style');"
            "    style.id = 'copilot-reader-style';"
            "    document.head.appendChild(style);"
            "  }"
            f"  style.textContent = {css!r};"
            "})();"
        )
        self.web_view.page().runJavaScript(script)

    def play_selected(self):
        index = self.chapter_list.currentRow()
        if index < 0 or index >= len(self.chapters):
            QtWidgets.QMessageBox.information(self, "Select Chapter", "Pick a chapter first.")
            return
        chapter = self.chapters[index]
        self._set_status(f"Synthesizing: {chapter['title']}")
        QtCore.QTimer.singleShot(50, lambda: self._start_playback(chapter["text"], chapter["title"]))

    def _start_playback(self, text, title):
        def worker():
            try:
                self.player.load_text(text)
                self.player.offset_ms = self.state.offset_ms
                self.player.play()
                self.status_changed.emit(f"Playing: {title}")
            except Exception as exc:
                print("TTS playback failed:", file=sys.stderr)
                traceback.print_exc()
                self.status_changed.emit("Ready")
                self.error_message.emit("TTS Error", f"Failed to synthesize:\n{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def pause(self):
        self.player.pause()
        self.state.offset_ms = self.player.get_offset_ms()
        self.state.save()
        self._set_status("Paused")

    def resume(self):
        self.player.resume()
        self._set_status("Playing")

    def stop(self):
        self.player.stop()
        self.state.offset_ms = 0
        self.state.save()
        self._set_status("Stopped")

    def closeEvent(self, event):
        self.state.offset_ms = self.player.get_offset_ms()
        self.state.save()
        self.player.stop()
        self._cleanup_book_dir()
        event.accept()

    def _cleanup_book_dir(self):
        if self.book_dir and os.path.isdir(self.book_dir):
            shutil.rmtree(self.book_dir, ignore_errors=True)
        self.book_dir = None

    def _extract_chapters(self, path):
        book = epub.read_epub(path)
        self._cleanup_book_dir()
        self.book_dir = tempfile.mkdtemp(prefix="epub_reader_")
        self._extract_items(book, self.book_dir)
        items_by_id = {item.id: item for item in book.get_items()}
        chapters = []
        for spine_id, _linear in book.spine:
            item = items_by_id.get(spine_id)
            if not item or item.get_type() != ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            title = self._chapter_title(soup, item.get_name())
            text = self._chapter_text(soup)
            if text.strip():
                html_path = os.path.join(self.book_dir, item.get_name())
                chapters.append({
                    "title": title,
                    "text": text,
                    "html_path": html_path,
                })
        if not chapters:
            raise ValueError("No readable chapters found.")
        return chapters

    def _extract_items(self, book, target_dir):
        for item in book.get_items():
            name = item.get_name()
            if not name:
                continue
            dest = os.path.join(target_dir, name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as handle:
                handle.write(item.get_content())

    @staticmethod
    def _chapter_title(soup, fallback):
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        header = soup.find(["h1", "h2", "h3"])
        if header and header.get_text(strip=True):
            return header.get_text(strip=True)
        return fallback or "Untitled"

    @staticmethod
    def _chapter_text(soup):
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    def _show_error(self, title, message):
        QtWidgets.QMessageBox.critical(self, title, message)
