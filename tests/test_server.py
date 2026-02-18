import threading
import time

from src.tts.server import TtsQueueController


class FakePlayer:
    def __init__(self, play_duration=0.02):
        self.is_playing = False
        self.is_paused = False
        self.play_duration = play_duration
        self.loaded_texts = []
        self.played_texts = []
        self.stop_calls = 0
        self._current_text = ""
        self._lock = threading.Lock()

    def load_text(self, text):
        with self._lock:
            self._current_text = text
            self.loaded_texts.append(text)

    def play(self):
        with self._lock:
            self.is_playing = True
            self.played_texts.append(self._current_text)
        threading.Thread(target=self._finish_playback, daemon=True).start()

    def _finish_playback(self):
        time.sleep(self.play_duration)
        with self._lock:
            self.is_playing = False

    def stop(self):
        with self._lock:
            self.stop_calls += 1
            self.is_playing = False
            self.is_paused = False


def _wait_until(predicate, timeout=1.0, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def test_speak_clears_queue_and_plays_immediately():
    player = FakePlayer(play_duration=0.05)
    controller = TtsQueueController(player, poll_interval=0.005)
    try:
        controller.add_to_queue("queued one")
        controller.add_to_queue("queued two")

        controller.speak("immediate text")

        assert player.played_texts[-1] == "immediate text"
        assert controller.queue_size() == 0
    finally:
        controller.shutdown()


def test_add_to_queue_plays_text_in_order():
    player = FakePlayer(play_duration=0.02)
    controller = TtsQueueController(player, poll_interval=0.005)
    try:
        controller.add_to_queue("first")
        controller.add_to_queue("second")

        completed = _wait_until(lambda: len(player.played_texts) >= 2)
        assert completed is True
        assert player.played_texts[:2] == ["first", "second"]
    finally:
        controller.shutdown()


def test_stop_clears_queue_and_stops_current_playback():
    player = FakePlayer(play_duration=0.10)
    controller = TtsQueueController(player, poll_interval=0.005)
    try:
        controller.speak("running")
        controller.add_to_queue("later")

        controller.stop()

        assert player.stop_calls >= 1
        assert player.is_playing is False
        assert controller.queue_size() == 0
    finally:
        controller.shutdown()
