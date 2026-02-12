import threading
import time

import keyboard
import numpy as np
import sounddevice as sd
import win32api
import win32clipboard
import win32con
from kokoro import KPipeline
from src.player import TtsPlayer

SAMPLE_RATE = 24000
VOICE = "af_heart"
SPEED = 1.2

speaking_lock = threading.Lock()
DEBUG = True


def _log(message):
    if DEBUG:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")


def _with_clipboard(action, retries=10, delay=0.05):
    for _ in range(retries):
        try:
            win32clipboard.OpenClipboard()
            try:
                return action()
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(delay)
    return None


def _save_clipboard():
    _log("Saving clipboard contents")
    def _read():
        items = []
        fmt = 0
        while True:
            fmt = win32clipboard.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            try:
                items.append((fmt, win32clipboard.GetClipboardData(fmt)))
            except TypeError:
                pass
        return items

    return _with_clipboard(_read) or []


def _restore_clipboard(saved_items):
    _log(f"Restoring clipboard with {len(saved_items)} formats")
    def _write():
        win32clipboard.EmptyClipboard()
        for fmt, value in saved_items:
            try:
                win32clipboard.SetClipboardData(fmt, value)
            except TypeError:
                pass

    _with_clipboard(_write)


def _get_clipboard_text():
    def _read():
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        return ""

    result = _with_clipboard(_read)
    text = result if isinstance(result, str) else ""
    _log(f"Clipboard text length: {len(text)}")
    return text


def _wait_for_clipboard_text(previous_text, previous_seq, timeout=1.0, interval=0.05):
    _log("Waiting for clipboard text to change")
    deadline = time.time() + timeout
    while time.time() < deadline:
        current_seq = win32clipboard.GetClipboardSequenceNumber()
        if current_seq != previous_seq:
            current = _get_clipboard_text()
            if current and current != previous_text:
                _log(f"Clipboard updated (length {len(current)})")
                return current
        time.sleep(interval)
    _log("Clipboard did not change before timeout")
    return _get_clipboard_text()


def _wait_for_hotkey_release(timeout=0.3, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not keyboard.is_pressed("alt") and not keyboard.is_pressed("`"):
            return True
        time.sleep(interval)
    return False


def _copy_selection():
    released = _wait_for_hotkey_release()
    _log(f"Hotkey released: {released}")
    _log("Sending Ctrl+C")
    win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(ord("C"), 0, 0, 0)
    win32api.keybd_event(ord("C"), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _handle_hotkey(player):
    player.stop()
    with speaking_lock:
        _log("Hotkey pressed")
        saved = _save_clipboard()
        previous_text = _get_clipboard_text()
        previous_seq = win32clipboard.GetClipboardSequenceNumber()
        _log(f"Clipboard sequence: {previous_seq}")
        _copy_selection()
        text = _wait_for_clipboard_text(previous_text, previous_seq)
        _restore_clipboard(saved)

        if text.strip():
            # Load and play new text
            player.load_text(text)
            player.play()
        else:
            _log("No text to speak")


def main():
    pipeline = KPipeline(lang_code="a")
    player = TtsPlayer(pipeline)

    keyboard.add_hotkey("alt+`", lambda: threading.Thread(
        target=_handle_hotkey, args=(player,), daemon=True
    ).start())

    print("Hotkey active: Alt+` (press Ctrl+C to exit)")
    keyboard.wait()


if __name__ == "__main__":
    main()
