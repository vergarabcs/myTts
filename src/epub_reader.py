import os
import sys
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk

from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from kokoro import KPipeline

from .player import TtsPlayer
from .state import ReaderState


class EpubReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EPUB Reader + Kokoro TTS")
        self.pipeline = KPipeline(lang_code="a")
        self.state = ReaderState()
        self.state.load()
        self.player = TtsPlayer(self.pipeline)
        self.player.on_state = self._update_controls
        self.chapters = []

        self._build_ui()
        self._load_saved_book()

    def _build_ui(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=8, pady=6)

        self.open_button = ttk.Button(toolbar, text="Open EPUB", command=self.open_epub)
        self.open_button.pack(side=tk.LEFT)

        self.play_button = ttk.Button(toolbar, text="Play", command=self.play_selected)
        self.play_button.pack(side=tk.LEFT, padx=6)

        self.pause_button = ttk.Button(toolbar, text="Pause", command=self.pause)
        self.pause_button.pack(side=tk.LEFT, padx=6)

        self.resume_button = ttk.Button(toolbar, text="Resume", command=self.resume)
        self.resume_button.pack(side=tk.LEFT, padx=6)

        self.stop_button = ttk.Button(toolbar, text="Stop", command=self.stop)
        self.stop_button.pack(side=tk.LEFT, padx=6)

        body = ttk.Frame(self.root)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.chapter_list = tk.Listbox(body, width=32)
        self.chapter_list.pack(side=tk.LEFT, fill=tk.Y)
        self.chapter_list.bind("<<ListboxSelect>>", lambda _event: self._show_chapter())

        self.text = tk.Text(body, wrap=tk.WORD)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)

        self.status = ttk.Label(self.root, text="Ready")
        self.status.pack(fill=tk.X, padx=8, pady=4)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_controls()

    def _set_status(self, message):
        self.status.configure(text=message)

    def _update_controls(self):
        if self.player.is_playing and not self.player.is_paused:
            self.play_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.NORMAL)
            self.resume_button.configure(state=tk.DISABLED)
        elif self.player.is_paused:
            self.play_button.configure(state=tk.DISABLED)
            self.pause_button.configure(state=tk.DISABLED)
            self.resume_button.configure(state=tk.NORMAL)
        else:
            self.play_button.configure(state=tk.NORMAL)
            self.pause_button.configure(state=tk.DISABLED)
            self.resume_button.configure(state=tk.DISABLED)
        can_stop = self.player.is_playing or self.player.is_paused or bool(self.player.text)
        self.stop_button.configure(state=tk.NORMAL if can_stop else tk.DISABLED)

    def _load_saved_book(self):
        if not self.state.book_path:
            return
        if not os.path.exists(self.state.book_path):
            return
        self._load_epub(self.state.book_path)
        if self.chapters:
            index = min(self.state.chapter_index, len(self.chapters) - 1)
            self.chapter_list.selection_set(index)
            self.chapter_list.see(index)
            self._show_chapter()

    def open_epub(self):
        path = filedialog.askopenfilename(
            filetypes=[("EPUB files", "*.epub")],
            title="Open EPUB",
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
            messagebox.showerror("EPUB Error", f"Failed to load EPUB:\n{exc}")
            return
        self.state.book_path = path
        self.state.chapter_index = 0
        self.state.offset_ms = 0
        self.state.save()
        self._refresh_chapter_list()
        self._show_chapter()
        self._set_status(f"Loaded: {os.path.basename(path)}")

    def _refresh_chapter_list(self):
        self.chapter_list.delete(0, tk.END)
        for title, _text in self.chapters:
            self.chapter_list.insert(tk.END, title)
        if self.chapters:
            self.chapter_list.selection_set(0)

    def _show_chapter(self):
        selection = self.chapter_list.curselection()
        if not selection:
            return
        index = selection[0]
        title, text = self.chapters[index]
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, text)
        self.state.chapter_index = index
        self.state.offset_ms = 0
        self.state.save()
        self.player.stop()
        self._set_status(f"Selected: {title}")

    def play_selected(self):
        selection = self.chapter_list.curselection()
        if not selection:
            messagebox.showinfo("Select Chapter", "Pick a chapter first.")
            return
        index = selection[0]
        title, text = self.chapters[index]
        self._set_status(f"Synthesizing: {title}")
        self.root.after(50, lambda: self._start_playback(text, title))

    def _start_playback(self, text, title):
        def worker():
            try:
                self.player.load_text(text)
                self.player.offset_ms = self.state.offset_ms
                self.player.play()
                self._set_status(f"Playing: {title}")
            except Exception as exc:
                print("TTS playback failed:", file=sys.stderr)
                traceback.print_exc()
                self._set_status("Ready")
                messagebox.showerror("TTS Error", f"Failed to synthesize:\n{exc}")

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

    def on_close(self):
        self.state.offset_ms = self.player.get_offset_ms()
        self.state.save()
        self.player.stop()
        self.root.destroy()

    def _extract_chapters(self, path):
        book = epub.read_epub(path)
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
                chapters.append((title, text))
        if not chapters:
            raise ValueError("No readable chapters found.")
        return chapters

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
