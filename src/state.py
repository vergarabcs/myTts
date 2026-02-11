import json
import os

from .constants import STATE_FILE


class ReaderState:
    def __init__(self):
        self.book_path = ""
        self.chapter_index = 0
        self.offset_ms = 0

    def load(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.book_path = data.get("book_path", "")
            self.chapter_index = int(data.get("chapter_index", 0))
            self.offset_ms = int(data.get("offset_ms", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    def save(self):
        data = {
            "book_path": self.book_path,
            "chapter_index": self.chapter_index,
            "offset_ms": self.offset_ms,
        }
        with open(STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
